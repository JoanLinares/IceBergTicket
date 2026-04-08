"""
MLService — Singleton que carga los artefactos entrenados y clasifica CSVs.

Artefactos necesarios en ML_ARTIFACTS_DIR:
  model_type_random_forest.pkl
  model_language_naive_bayes.pkl
  model_snowflake_gradient_boosting.pkl
  scaler.pkl
  label_encoders.pkl
  tfidf_vectorizer.pkl
  model_metadata.pkl
"""
import os
import io
import joblib
import pickle
import numpy as np
import pandas as pd

ARTIFACTS_DIR = os.getenv(
    "ML_ARTIFACTS_DIR",
    os.path.join(os.path.dirname(__file__), '..', '..', 'ml', 'model_artifacts')
)

# Aliases de columnas: mapea nombres estándar a posibles variantes en el CSV
_COL_ALIASES = {
    'subject':          ['subject', 'title', 'summary', 'asunto'],
    'body':             ['body', 'description', 'message', 'text', 'content', 'descripcion', 'mensaje'],
    'priority':         ['priority', 'prioridad'],
    'queue':            ['queue', 'department', 'category', 'departamento'],
    'language':         ['language', 'lang', 'idioma'],
    'submitter_email':  ['submitter_email', 'email', 'from_email', 'customer_email', 'correo'],
    'submitter_name':   ['submitter_name', 'name', 'customer_name', 'nombre'],
    'agent_name':       ['agent_name', 'assigned_to', 'assignee', 'agente'],
    'created_at':       ['created_at', 'created', 'date', 'timestamp', 'fecha'],
    'status':           ['status', 'estado'],
}


def _find_col(df: pd.DataFrame, key: str) -> str | None:
    """Devuelve el nombre real de la columna en df para la clave estándar, o None."""
    for alias in _COL_ALIASES.get(key, [key]):
        if alias in df.columns:
            return alias
    return None


class MLService:
    """
    Singleton — los modelos solo se cargan una vez por proceso.
    Uso: MLService.get_instance().classify_csv(csv_bytes)
    """
    _instance = None

    def __init__(self):
        metadata_path = os.path.join(ARTIFACTS_DIR, 'model_metadata.pkl')
        self.metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)

        self.type_feature_mode = (
            self.metadata.get('feature_modes', {}).get('type', 'combined_scaled')
        )

        self.scaler = joblib.load(os.path.join(ARTIFACTS_DIR, 'scaler.pkl'))
        self.tfidf = joblib.load(os.path.join(ARTIFACTS_DIR, 'tfidf_vectorizer.pkl'))
        self.label_encoders = joblib.load(os.path.join(ARTIFACTS_DIR, 'label_encoders.pkl'))
        self.model_type = joblib.load(os.path.join(ARTIFACTS_DIR, 'model_type_random_forest.pkl'))
        self.model_language = joblib.load(os.path.join(ARTIFACTS_DIR, 'model_language_naive_bayes.pkl'))
        self.model_snowflake = joblib.load(os.path.join(ARTIFACTS_DIR, 'model_snowflake_gradient_boosting.pkl'))

        self.tfidf_type = None
        tfidf_type_file = self.metadata.get('model_files', {}).get('tfidf_type')
        if self.type_feature_mode == 'text_tfidf_only':
            candidate = tfidf_type_file or 'tfidf_vectorizer_type.pkl'
            tfidf_type_path = os.path.join(ARTIFACTS_DIR, candidate)
            if os.path.exists(tfidf_type_path):
                self.tfidf_type = joblib.load(tfidf_type_path)
            else:
                # Fallback seguro para no romper predicción si falta el artefacto nuevo.
                self.type_feature_mode = 'combined_scaled'

    @classmethod
    def get_instance(cls) -> 'MLService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def classify_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clasifica un DataFrame ya cargado en memoria.

        Añade:
                    pred_type     → categoría/tipo de ticket (categorías explícitas)
          pred_language → idioma          (en / es / de / fr / pt)
          pred_level    → nivel DW        (BASIC / MEDIUM / PRO)
        """
        combined = self._get_text_combined(df)
        X = self._build_features(df, combined)

        # Models were trained with string labels (y_type, y_language, y_snowflake
        # are raw string arrays), so predict() already returns strings directly.
        # label_encoders only encodes INPUT features (queue/priority/language),
        # it is NOT used to decode model output predictions.
        if self.type_feature_mode == 'text_tfidf_only' and self.tfidf_type is not None:
            X_type = self.tfidf_type.transform(combined)
            pred_type = self.model_type.predict(X_type)
        else:
            pred_type = self.model_type.predict(X)
        pred_lang = self.model_language.predict(X)
        pred_snow = self.model_snowflake.predict(X)

        out = df.copy()
        out['pred_type'] = pred_type
        out['pred_language'] = pred_lang
        out['pred_level'] = pred_snow
        return out

    def classify_csv(self, csv_bytes: bytes) -> pd.DataFrame:
        """
        Lee un CSV y añade tres columnas:
                    pred_type     → categoría/tipo de ticket (categorías explícitas)
          pred_language → idioma          (en / es / de / fr / pt)
          pred_level    → nivel DW        (BASIC / MEDIUM / PRO)

        Returns:
            DataFrame original + columnas de predicción.
        """
        df = pd.read_csv(io.BytesIO(csv_bytes))
        return self.classify_dataframe(df)

    # ------------------------------------------------------------------
    # Construcción de features (compatible con el entrenamiento)
    # ------------------------------------------------------------------

    def _get_text_combined(self, df: pd.DataFrame) -> pd.Series:
        """Construye texto combinado subject+body para inferencia."""
        n = len(df)
        subj_col = _find_col(df, 'subject')
        body_col = _find_col(df, 'body')
        subj_s = df[subj_col].fillna('') if subj_col else pd.Series([''] * n)
        body_s = df[body_col].fillna('') if body_col else pd.Series([''] * n)
        return (subj_s + ' ' + body_s).str.strip()

    def _build_features(self, df: pd.DataFrame, combined: pd.Series | None = None) -> np.ndarray:
        n        = len(df)
        expected = self.scaler.n_features_in_

        # Texto combinado → TF-IDF
        subj_col = _find_col(df, 'subject')
        body_col = _find_col(df, 'body')
        subj_s = df[subj_col].fillna('') if subj_col else pd.Series([''] * n)
        body_s = df[body_col].fillna('') if body_col else pd.Series([''] * n)
        if combined is None:
            combined = (subj_s + ' ' + body_s).str.strip()

        tfidf_arr = self.tfidf.transform(combined).toarray()   # (n, 100)

        # Features de longitud
        length_arr = np.column_stack([
            subj_s.str.len().values,
            body_s.str.len().values,
            combined.str.len().values,
            combined.str.split().str.len().fillna(0).astype(int).values,
        ])                                                      # (n, 4)

        # Features categóricas (solo las que existen en el CSV)
        cat_parts = []
        for col in ['queue', 'priority', 'language']:
            real = _find_col(df, col)
            if real and col in self.label_encoders:
                le  = self.label_encoders[col]
                enc = df[real].fillna('unknown').map(
                    lambda x, _le=le: int(_le.transform([x])[0]) if x in _le.classes_ else -1
                ).values.reshape(-1, 1)
                cat_parts.append(enc)

        parts = cat_parts + [length_arr, tfidf_arr]
        X = np.hstack(parts).astype(float)

        # Ajustar al número de features esperado por el scaler
        if X.shape[1] < expected:
            X = np.hstack([X, np.zeros((n, expected - X.shape[1]))])
        elif X.shape[1] > expected:
            X = X[:, :expected]

        return self.scaler.transform(X)
