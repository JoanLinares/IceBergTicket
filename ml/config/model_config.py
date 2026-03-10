"""
Configuración para el sistema ML de tickets
"""

# Configuración del modelo
MODEL_CONFIG = {
    # TF-IDF
    'tfidf': {
        'max_features': 100,
        'min_df': 2,
        'max_df': 0.8,
        'ngram_range': (1, 2),
        'stop_words': 'english'
    },
    
    # Random Forest
    'random_forest': {
        'n_estimators': 100,
        'max_depth': None,
        'min_samples_split': 2,
        'min_samples_leaf': 1,
        'class_weight': 'balanced',
        'random_state':42,
        'n_jobs': -1
    },
    
    # Gradient Boosting
    'gradient_boosting': {
        'n_estimators': 100,
        'learning_rate': 0.1,
        'max_depth': 3,
        'random_state': 42
    },
    
    # Logistic Regression
    'logistic_regression': {
        'max_iter': 1000,
        'class_weight': 'balanced',
        'random_state': 42,
        'n_jobs': -1
    },
    
    # LinearSVC (misma matemática que SVM lineal, 10-100x más rápido)
    'linear_svc': {
        'dual': 'auto',
        'class_weight': 'balanced',
        'random_state': 42
    },

    # Naive Bayes (detección de idioma)
    'naive_bayes': {},
    
    # Train/Test split
    'train_test_split': {
        'test_size': 0.2,
        'random_state': 42,
        'stratify': True
    },
    
    # Cross Validation
    'cross_validation': {
        'n_splits': 5,
        'shuffle': True,
        'random_state': 42
    }
}

# Configuración de features
FEATURE_CONFIG = {
    'categorical_features': ['queue', 'priority', 'language'],
    'text_features': ['subject', 'body'],
    'numerical_features': ['subject_length', 'body_length', 'text_length', 'word_count']
}

# Configuración de Snowflake
SNOWFLAKE_CONFIG = {
    'complexity_thresholds': {
        'BASIC': {'min_score': 0, 'max_score': 5},
        'MEDIUM': {'min_score': 6, 'max_score': 9},
        'PRO': {'min_score': 10, 'max_score': 15}
    },
    'scoring_criteria': {
        'high_columns': {'threshold': 20, 'score': 3},
        'medium_columns': {'threshold': 12, 'score': 2},
        'low_columns': {'threshold': 0, 'score': 1},
        'high_volume': {'threshold': 50000, 'score': 3},
        'medium_volume': {'threshold': 10000, 'score': 2},
        'low_volume': {'threshold': 0, 'score': 1},
        'many_tags': {'threshold': 5, 'score': 2},
        'some_tags': {'threshold': 1, 'score': 1},
        'has_product': {'score': 1},
        'has_segments': {'score': 1},
        'has_sla': {'score': 1}
    }
}

# Mapeo de idiomas
LANGUAGE_MAP = {
    'en': 'Inglés',
    'es': 'Español',
    'de': 'Alemán',
    'fr': 'Francés',
    'pt': 'Portugués',
    'unknown': 'Desconocido'
}

# Qué modelo maneja cada tarea (debe coincidir con los .pkl guardados)
TASK_MODELS = {
    'type':      'Random Forest',
    'language':  'Naive Bayes',
    'snowflake': 'Gradient Boosting',
}

# Nombres fijos de los artefactos guardados en model_artifacts/
SAVED_MODEL_FILES = {
    'type':           'model_type_random_forest.pkl',
    'language':       'model_language_naive_bayes.pkl',
    'snowflake':      'model_snowflake_gradient_boosting.pkl',
    'scaler':         'scaler.pkl',
    'label_encoders': 'label_encoders.pkl',
    'tfidf':          'tfidf_vectorizer.pkl',
    'metadata':       'model_metadata.pkl',
}

# Paths
PATHS = {
    'data_dir':        '../data',
    'raw_data':        '../data/raw',
    'processed_data':  '../data/processed',
    'model_artifacts': '../model_artifacts',
    'db_basic':        '../model_artifacts/basic_dw.db',
    'db_medium':       '../model_artifacts/medium_dw.db',
    'db_pro':          '../model_artifacts/pro_dw.db',
}
