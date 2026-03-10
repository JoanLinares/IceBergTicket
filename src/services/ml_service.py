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
    'body':             ['body', 'description', 'message', 'content', 'descripcion', 'mensaje'],
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
        self.scaler          = joblib.load(os.path.join(ARTIFACTS_DIR, 'scaler.pkl'))
        self.tfidf           = joblib.load(os.path.join(ARTIFACTS_DIR, 'tfidf_vectorizer.pkl'))
        self.label_encoders  = joblib.load(os.path.join(ARTIFACTS_DIR, 'label_encoders.pkl'))
        self.model_type      = joblib.load(os.path.join(ARTIFACTS_DIR, 'model_type_random_forest.pkl'))
        self.model_language  = joblib.load(os.path.join(ARTIFACTS_DIR, 'model_language_naive_bayes.pkl'))
        self.model_snowflake = joblib.load(os.path.join(ARTIFACTS_DIR, 'model_snowflake_gradient_boosting.pkl'))
        with open(os.path.join(ARTIFACTS_DIR, 'model_metadata.pkl'), 'rb') as f:
            self.metadata = pickle.load(f)

    @classmethod
    def get_instance(cls) -> 'MLService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def classify_csv(self, csv_bytes: bytes) -> pd.DataFrame:
        """
        Lee un CSV y añade tres columnas:
          pred_type     → tipo de ticket  (Incident / Request / Problem)
          pred_language → idioma          (en / es / de / fr / pt)
          pred_level    → nivel DW        (BASIC / MEDIUM / PRO)

        Returns:
            DataFrame original + columnas de predicción.
        """
        df = pd.read_csv(io.BytesIO(csv_bytes))
        X  = self._build_features(df)

        pred_type = self.model_type.predict(X)
        pred_lang = self.model_language.predict(X)
        pred_snow = self.model_snowflake.predict(X)

        # Decodificar etiquetas
        le = self.label_encoders
        if 'type'      in le: pred_type = le['type'].inverse_transform(pred_type)
        if 'language'  in le: pred_lang = le['language'].inverse_transform(pred_lang)
        if 'snowflake' in le: pred_snow = le['snowflake'].inverse_transform(pred_snow)

        out = df.copy()
        out['pred_type']     = pred_type
        out['pred_language'] = pred_lang
        out['pred_level']    = pred_snow
        return out

    # ------------------------------------------------------------------
    # Construcción de features (compatible con el entrenamiento)
    # ------------------------------------------------------------------

    def _build_features(self, df: pd.DataFrame) -> np.ndarray:
        n        = len(df)
        expected = self.scaler.n_features_in_

        # Texto combinado → TF-IDF
        subj_col = _find_col(df, 'subject')
        body_col = _find_col(df, 'body')
        subj_s   = df[subj_col].fillna('') if subj_col else pd.Series([''] * n)
        body_s   = df[body_col].fillna('') if body_col else pd.Series([''] * n)
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
