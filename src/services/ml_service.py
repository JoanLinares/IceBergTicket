"""
MLService: singleton that loads trained artifacts and classifies CSV/dataframes.
"""
import os
import io
import joblib
import pickle
import fnmatch
import re
import unicodedata
import numpy as np
import pandas as pd

ARTIFACTS_DIR = os.getenv(
    "ML_ARTIFACTS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "ml", "model_artifacts"),
)

_COL_ALIASES = {
    "subject": ["subject", "title", "summary", "asunto"],
    "body": ["body", "description", "message", "text", "content", "descripcion", "mensaje"],
    "priority": ["priority", "prioridad"],
    "queue": ["queue", "department", "category", "departamento"],
    "language": ["language", "lang", "idioma"],
    "submitter_email": ["submitter_email", "email", "from_email", "customer_email", "correo"],
    "submitter_name": ["submitter_name", "name", "customer_name", "nombre"],
    "agent_name": ["agent_name", "assigned_to", "assignee", "agente"],
    "created_at": ["created_at", "created", "date", "timestamp", "fecha"],
    "status": ["status", "estado"],
}

_SUPPORTED_LANG_CODES = {"en", "es", "de", "fr", "pt"}
_LANGUAGE_NAME_TO_CODE = {
    "english": "en",
    "ingles": "en",
    "spanish": "es",
    "espanol": "es",
    "german": "de",
    "deutsch": "de",
    "aleman": "de",
    "french": "fr",
    "francais": "fr",
    "frances": "fr",
    "portuguese": "pt",
    "portugues": "pt",
}
_LANGUAGE_STOPWORDS = {
    "en": {
        "the", "and", "for", "with", "not", "this", "that", "from", "have",
        "account", "login", "password", "payment", "error", "cannot",
    },
    "es": {
        "el", "la", "de", "que", "para", "con", "por", "una", "tengo",
        "cuenta", "acceso", "pago", "cobro", "error", "facturacion",
        "hola", "necesito", "ayuda", "integracion", "herramienta",
        "actualmente", "estamos", "sistemas", "sincronizacion", "algunos",
        "datos", "despues", "hemos", "revisado", "configuracion",
        "credenciales", "podrian", "pasos", "debemos", "gracias",
    },
    "de": {
        "der", "die", "das", "und", "nicht", "mit", "ein", "eine", "ist",
        "konto", "zugang", "zahlung", "fehler", "verbindung", "netzwerk",
    },
    "fr": {
        "le", "la", "de", "et", "pas", "pour", "avec", "une", "compte",
        "acces", "paiement", "erreur", "connexion",
    },
    "pt": {
        "o", "a", "de", "que", "para", "com", "uma", "conta", "acesso",
        "pagamento", "cobranca", "erro", "conexao",
        "ola", "preciso", "ajuda", "integracao", "ferramenta",
        "atualmente", "estamos", "sincronizacao", "alguns", "dados",
        "depois", "revisamos", "configuracao", "credenciais",
        "poderiam", "passos", "devemos", "obrigado",
    },
}
_TOKEN_RE = re.compile(r"[a-z]{2,}")

try:
    from langdetect import DetectorFactory, LangDetectException, detect_langs

    DetectorFactory.seed = 0
    _HAS_LANGDETECT = True
except Exception:
    LangDetectException = Exception
    detect_langs = None
    _HAS_LANGDETECT = False


def _find_col(df: pd.DataFrame, key: str) -> str | None:
    for alias in _COL_ALIASES.get(key, [key]):
        if alias in df.columns:
            return alias
    return None


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize_language_code(value) -> str | None:
    if value is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    if "-" in text:
        text = text.split("-", 1)[0]
    if text in _SUPPORTED_LANG_CODES:
        return text

    normalized = _strip_accents(text)
    if normalized in _SUPPORTED_LANG_CODES:
        return normalized
    return _LANGUAGE_NAME_TO_CODE.get(normalized)


def _detect_language_heuristic(text: str) -> str | None:
    raw = text.lower()
    normalized = _strip_accents(raw)
    tokens = _TOKEN_RE.findall(normalized)
    if len(tokens) < 4:
        return None

    scores = {
        code: sum(1 for tok in tokens if tok in words)
        for code, words in _LANGUAGE_STOPWORDS.items()
    }

    # Explicit tie-breaker for Spanish vs Portuguese.
    es_markers = {
        "necesito", "ayuda", "herramienta", "sincronizacion", "algunos",
        "despues", "hemos", "revisado", "credenciales", "podrian", "gracias",
    }
    pt_markers = {
        "preciso", "ajuda", "ferramenta", "sincronizacao", "alguns",
        "depois", "revisamos", "credenciais", "poderiam", "obrigado",
    }
    scores["es"] += 2 * sum(1 for tok in tokens if tok in es_markers)
    scores["pt"] += 2 * sum(1 for tok in tokens if tok in pt_markers)

    # Language-specific symbols.
    if any(ch in raw for ch in "\u00e4\u00f6\u00fc\u00df"):
        scores["de"] += 2
    if any(ch in raw for ch in "\u00f1\u00bf\u00a1"):
        scores["es"] += 2
    if any(ch in raw for ch in "\u00e7\u00e3\u00f5"):
        scores["pt"] += 2
    if any(ch in raw for ch in "\u00e0\u00e2\u00e6\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u0153\u00f9\u00fb\u00ff"):
        scores["fr"] += 2

    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]
    if best_score <= 0:
        return None

    sorted_scores = sorted(scores.values(), reverse=True)
    runner_up = sorted_scores[1] if len(sorted_scores) > 1 else 0
    if best_score - runner_up < 2 and best_score < 4:
        return None
    return best_lang


def _detect_language_from_text(text: str) -> str | None:
    if text is None:
        return None

    clean = " ".join(str(text).split())
    if len(clean) < 15:
        return None

    heuristic = _detect_language_heuristic(clean)
    if heuristic:
        return heuristic

    if not _HAS_LANGDETECT:
        return None

    try:
        candidates = detect_langs(clean)
    except LangDetectException:
        return None
    except Exception:
        return None

    if not candidates:
        return None

    top = candidates[0]
    lang = _normalize_language_code(getattr(top, "lang", None))
    prob = float(getattr(top, "prob", 0.0))
    if not lang:
        return None

    if prob < 0.65 and len(clean) < 80:
        return None
    return lang


class MLService:
    _instance = None

    def __init__(self):
        metadata_path = os.path.join(ARTIFACTS_DIR, "model_metadata.pkl")
        self.metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, "rb") as f:
                self.metadata = pickle.load(f)

        model_files = self.metadata.get("model_files", {}) if isinstance(self.metadata, dict) else {}
        self.type_feature_mode = self.metadata.get("feature_modes", {}).get("type", "combined_scaled")

        self.scaler = joblib.load(os.path.join(ARTIFACTS_DIR, "scaler.pkl"))
        self.tfidf = joblib.load(os.path.join(ARTIFACTS_DIR, "tfidf_vectorizer.pkl"))
        self.label_encoders = joblib.load(os.path.join(ARTIFACTS_DIR, "label_encoders.pkl"))
        self.model_type = self._load_model_artifact(
            preferred_file=model_files.get("type"),
            fallback_exact=["model_type_random_forest.pkl"],
            fallback_patterns=["model_type_*.pkl"],
        )
        self.model_language = self._load_model_artifact(
            preferred_file=model_files.get("language"),
            fallback_exact=["model_language_naive_bayes.pkl"],
            fallback_patterns=["model_language_*.pkl"],
        )
        self.model_snowflake = self._load_model_artifact(
            preferred_file=model_files.get("snowflake"),
            fallback_exact=["model_snowflake_gradient_boosting.pkl"],
            fallback_patterns=["model_snowflake_*.pkl"],
        )

        self.tfidf_type = None
        tfidf_type_file = self.metadata.get("model_files", {}).get("tfidf_type")
        if self.type_feature_mode == "text_tfidf_only":
            candidate = tfidf_type_file or "tfidf_vectorizer_type.pkl"
            tfidf_type_path = os.path.join(ARTIFACTS_DIR, candidate)
            if os.path.exists(tfidf_type_path):
                self.tfidf_type = joblib.load(tfidf_type_path)
            else:
                self.type_feature_mode = "combined_scaled"

    def _load_model_artifact(
        self,
        preferred_file: str | None,
        fallback_exact: list[str] | None = None,
        fallback_patterns: list[str] | None = None,
    ):
        fallback_exact = fallback_exact or []
        fallback_patterns = fallback_patterns or []

        candidate_names = []
        if preferred_file:
            candidate_names.append(preferred_file)
        candidate_names.extend(fallback_exact)

        for name in candidate_names:
            path = os.path.join(ARTIFACTS_DIR, name)
            if os.path.exists(path):
                return joblib.load(path)

        try:
            files = sorted(os.listdir(ARTIFACTS_DIR))
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"No existe directorio de artefactos: {ARTIFACTS_DIR}") from exc

        for pattern in fallback_patterns:
            for filename in files:
                if fnmatch.fnmatch(filename, pattern):
                    return joblib.load(os.path.join(ARTIFACTS_DIR, filename))

        searched = ", ".join(candidate_names + fallback_patterns)
        raise FileNotFoundError(f"No se encontro artefacto de modelo. Buscado: {searched}")

    @classmethod
    def get_instance(cls) -> "MLService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def classify_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        combined = self._get_text_combined(df)
        X = self._build_features(df, combined)

        if self.type_feature_mode == "text_tfidf_only" and self.tfidf_type is not None:
            X_type = self.tfidf_type.transform(combined)
            pred_type = self.model_type.predict(X_type)
        else:
            pred_type = self.model_type.predict(X)
        pred_lang_model = self.model_language.predict(X)
        pred_snow = self.model_snowflake.predict(X)

        lang_col = _find_col(df, "language")
        if lang_col:
            lang_input = df[lang_col].tolist()
        else:
            lang_input = [None] * len(df)

        pred_lang = []
        for text_value, input_value, model_value in zip(
            combined.tolist(),
            lang_input,
            pred_lang_model.tolist(),
        ):
            text_lang = _detect_language_from_text(text_value)
            input_lang = _normalize_language_code(input_value)
            model_lang = _normalize_language_code(model_value)
            pred_lang.append(text_lang or input_lang or model_lang or "unknown")

        out = df.copy()
        out["pred_type"] = pred_type
        out["pred_language"] = pred_lang
        out["pred_level"] = pred_snow
        return out

    def classify_csv(self, csv_bytes: bytes) -> pd.DataFrame:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        return self.classify_dataframe(df)

    def _get_text_combined(self, df: pd.DataFrame) -> pd.Series:
        n = len(df)
        subj_col = _find_col(df, "subject")
        body_col = _find_col(df, "body")
        subj_s = df[subj_col].fillna("") if subj_col else pd.Series([""] * n)
        body_s = df[body_col].fillna("") if body_col else pd.Series([""] * n)
        return (subj_s + " " + body_s).str.strip()

    def _build_features(self, df: pd.DataFrame, combined: pd.Series | None = None) -> np.ndarray:
        n = len(df)
        expected = self.scaler.n_features_in_

        subj_col = _find_col(df, "subject")
        body_col = _find_col(df, "body")
        subj_s = df[subj_col].fillna("") if subj_col else pd.Series([""] * n)
        body_s = df[body_col].fillna("") if body_col else pd.Series([""] * n)
        if combined is None:
            combined = (subj_s + " " + body_s).str.strip()

        tfidf_arr = self.tfidf.transform(combined).toarray()

        length_arr = np.column_stack(
            [
                subj_s.str.len().values,
                body_s.str.len().values,
                combined.str.len().values,
                combined.str.split().str.len().fillna(0).astype(int).values,
            ]
        )

        cat_parts = []
        for col in ["queue", "priority", "language"]:
            real = _find_col(df, col)
            if real and col in self.label_encoders:
                le = self.label_encoders[col]
                enc = (
                    df[real]
                    .fillna("unknown")
                    .map(lambda x, _le=le: int(_le.transform([x])[0]) if x in _le.classes_ else -1)
                    .values.reshape(-1, 1)
                )
                cat_parts.append(enc)
            else:
                cat_parts.append(np.full((n, 1), -1))

        parts = cat_parts + [length_arr, tfidf_arr]
        X = np.hstack(parts).astype(float)

        if X.shape[1] < expected:
            X = np.hstack([X, np.zeros((n, expected - X.shape[1]))])
        elif X.shape[1] > expected:
            X = X[:, :expected]

        return self.scaler.transform(X)
