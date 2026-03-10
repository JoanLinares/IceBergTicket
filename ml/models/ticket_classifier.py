"""
Ticket Classifier Module

Multi-objetivo: predice tres tareas simultáneamente:
1. Tipo de ticket  (Incident / Request / Problem)   → Random Forest
2. Idioma          (en / es / de / fr / pt)          → Naive Bayes
3. Nivel Snowflake (BASIC / MEDIUM / PRO)            → Gradient Boosting

Artefactos esperados en model_artifacts/:
  model_type_random_forest.pkl
  model_language_naive_bayes.pkl
  model_snowflake_gradient_boosting.pkl
  scaler.pkl
  label_encoders.pkl
  tfidf_vectorizer.pkl
  model_metadata.pkl
"""

import os
import joblib
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime

from .preprocessor import TicketPreprocessor


class TicketClassifier:
    """
    Clasificador multi-objetivo de tickets.

    Carga los artefactos entrenados desde model_artifacts/ y expone:
      predict(ticket_dict)       → type, language, snowflake_level + confianzas
      predict_batch(list[dict])  → lista de predicciones
      get_model_info()           → metadata del entrenamiento
    """

    def __init__(self, model_path: str, timestamp: Optional[str] = None):
        """
        Args:
            model_path: Directorio con los .pkl entrenados (model_artifacts/).
            timestamp:  No usado — mantenido por compatibilidad.
        """
        self.model_path = model_path
        self.timestamp = timestamp

        self.model_type      = None
        self.model_language  = None
        self.model_snowflake = None
        self.scaler          = None
        self.label_encoders  = None   # decodificadores de etiquetas de salida
        self.tfidf           = None   # TF-IDF vectorizer para texto de entrada
        self.metadata        = None

        self._load_models()
        self._init_preprocessor()

    # ------------------------------------------------------------------
    # Inicialización interna
    # ------------------------------------------------------------------

    def _init_preprocessor(self):
        """Inyecta el TF-IDF cargado en un TicketPreprocessor."""
        self.preprocessor = TicketPreprocessor()
        if self.tfidf is not None:
            self.preprocessor.tfidf     = self.tfidf
            self.preprocessor.is_fitted = True

    def _load_models(self):
        """Carga todos los artefactos .pkl desde model_path."""
        try:
            model_files = [f for f in os.listdir(self.model_path) if f.endswith('.pkl')]
            if not model_files:
                raise FileNotFoundError(f"No se encontraron .pkl en {self.model_path}")

            for file in model_files:
                filepath = os.path.join(self.model_path, file)

                if 'model_type' in file:
                    self.model_type = joblib.load(filepath)
                    print(f"✅ Cargado clasificador tipo:      {file}")

                elif 'model_language' in file:
                    self.model_language = joblib.load(filepath)
                    print(f"✅ Cargado clasificador idioma:    {file}")

                elif 'model_snowflake' in file:
                    self.model_snowflake = joblib.load(filepath)
                    print(f"✅ Cargado clasificador snowflake: {file}")

                elif file == 'scaler.pkl':
                    self.scaler = joblib.load(filepath)
                    print(f"✅ Cargado scaler:                 {file}")

                elif file == 'label_encoders.pkl':
                    self.label_encoders = joblib.load(filepath)
                    print(f"✅ Cargados label encoders:        {file}")

                elif file == 'tfidf_vectorizer.pkl':
                    self.tfidf = joblib.load(filepath)
                    print(f"✅ Cargado TF-IDF vectorizer:      {file}")

                elif 'metadata' in file:
                    with open(filepath, 'rb') as f:
                        self.metadata = pickle.load(f)
                    print(f"✅ Cargada metadata:               {file}")

            # Verificar artefactos obligatorios
            missing = []
            if not self.model_type:      missing.append('model_type_*.pkl')
            if not self.model_language:  missing.append('model_language_*.pkl')
            if not self.model_snowflake: missing.append('model_snowflake_*.pkl')
            if not self.scaler:          missing.append('scaler.pkl')
            if not self.tfidf:           missing.append('tfidf_vectorizer.pkl')
            if missing:
                raise ValueError(f"Artefactos faltantes: {', '.join(missing)}")

        except Exception as e:
            raise RuntimeError(f"Error cargando modelos: {str(e)}")

    # ------------------------------------------------------------------
    # Preprocesado
    # ------------------------------------------------------------------

    def preprocess(self, ticket_data: Dict[str, Any]) -> np.ndarray:
        """
        Convierte un ticket (dict) en el vector de features sin escalar.

        Args:
            ticket_data: dict con campos: subject, body, priority, queue, ...

        Returns:
            np.ndarray de shape (1, n_features).
        """
        return self.preprocessor.preprocess_single(ticket_data)

    # ------------------------------------------------------------------
    # Predicción
    # ------------------------------------------------------------------

    def predict(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predice tipo, idioma y nivel snowflake para un ticket.

        Args:
            ticket_data: dict con campos del ticket.

        Returns:
            dict con 'type', 'language', 'snowflake_level',
            'confidence_scores' y 'timestamp'.
        """
        X        = self.preprocess(ticket_data)
        X_scaled = self.scaler.transform(X.reshape(1, -1))

        type_pred      = self.model_type.predict(X_scaled)[0]
        language_pred  = self.model_language.predict(X_scaled)[0]
        snowflake_pred = self.model_snowflake.predict(X_scaled)[0]

        # Decodificar etiquetas numéricas → strings
        # label_encoders only has input feature encoders (queue/priority/language),
        # NOT output class decoders. Models trained with string labels output
        # strings directly, so no inverse_transform is needed or correct here.
        if self.label_encoders:
            pass  # intentionally left; models return strings directly

        return {
            'type':            str(type_pred),
            'language':        str(language_pred),
            'snowflake_level': str(snowflake_pred),
            'confidence_scores': {
                'type':      self._get_confidence(self.model_type,      X_scaled),
                'language':  self._get_confidence(self.model_language,  X_scaled),
                'snowflake': self._get_confidence(self.model_snowflake, X_scaled),
            },
            'timestamp': datetime.now().isoformat()
        }

    def _get_confidence(self, model, X_scaled: np.ndarray) -> Optional[List[float]]:
        """
        Devuelve puntuaciones de confianza normalizadas [0, 1].
          - RF / GB / NB (predict_proba):  probabilidades directas.
          - LinearSVC (decision_function): softmax para normalizar.
        """
        if hasattr(model, 'predict_proba'):
            return model.predict_proba(X_scaled)[0].tolist()
        if hasattr(model, 'decision_function'):
            scores = model.decision_function(X_scaled)[0]
            if np.ndim(scores) == 0:
                return [float(scores)]
            exp_s = np.exp(scores - scores.max())
            return (exp_s / exp_s.sum()).tolist()
        return None

    def predict_batch(self, tickets: list) -> list:
        """Predice para una lista de tickets."""
        return [self.predict(t) for t in tickets]

    def get_model_info(self) -> Dict[str, Any]:
        """Devuelve información/metadata sobre los modelos cargados."""
        if self.metadata:
            return self.metadata
        return {
            'type_model':      type(self.model_type).__name__,
            'language_model':  type(self.model_language).__name__,
            'snowflake_model': type(self.model_snowflake).__name__,
            'tfidf_loaded':    self.tfidf is not None,
            'loaded_at':       datetime.now().isoformat()
        }


# Uso de ejemplo
if __name__ == "__main__":
    classifier = TicketClassifier(model_path='../model_artifacts/')

    ticket = {
        'subject':  'Cannot access my account',
        'body':     'I am unable to log in to my account. I get an error message.',
        'priority': 'high',
        'queue':    'technical_support',
    }

    result = classifier.predict(ticket)

    print("\n" + "="*80)
    print("RESULTADOS DE PREDICCIÓN")
    print("="*80)
    print(f"\nTipo de ticket:  {result['type']}")
    print(f"Idioma:          {result['language']}")
    print(f"Nivel Snowflake: {result['snowflake_level']}")
    print(f"\nConfianza: {result['confidence_scores']}")
