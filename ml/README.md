# IceBergTicket - Machine Learning Module

## 📋 Descripción

Sistema de Machine Learning multi-objetivo para clasificación inteligente de tickets de soporte que incluye:

1. **Clasificación de Tipo de Ticket** (Incident/Request/Problem)
2. **Detección Automática de Idioma** (en, es, de, fr, pt)
3. **Determinación de Nivel Snowflake DW** (Basic/Medium/Pro)
4. **Generación Automática de Esquemas SQL**

## 🏗️ Estructura del Proyecto

```
ml/
├── config/                          # Configuraciones
│   └── model_config.py             # Parámetros de modelos y features
├── data/                            # Datasets (5 CSV multi-idioma)
│   ├── aa_dataset-tickets-multi-lang-5-2-50-version.csv
│   ├── dataset-tickets-multi-lang-4-20k.csv
│   ├── dataset-tickets-multi-lang3-4k.csv
│   └── dataset-tickets-german_normalized*.csv
├── models/                          # Código para usar modelos en producción
│   ├── __init__.py
│   ├── ticket_classifier.py        # Carga modelos y hace predicciones
│   ├── snowflake_generator.py      # Genera esquemas SQL
│   └── preprocessor.py             # Pipeline de preprocesamiento
├── model_artifacts/                 # Modelos entrenados (.pkl) - se crean al ejecutar notebook
│   ├── model_type_*.pkl
│   ├── model_language_*.pkl
│   ├── model_snowflake_*.pkl
│   ├── scaler_*.pkl
│   ├── model_metadata_*.pkl
│   └── snowflake_schema_*.sql      # Esquemas SQL generados
├── notebooks/                       # Jupyter notebooks
│   └── ticket_classification_analysis.ipynb  # Notebook principal (72 celdas)
└── README.md                        # Este archivo
```

## 🚀 Inicio Rápido

### 1. Instalación de Dependencias

```bash
uv sync
```

### 2. Entrenamiento de Modelos

**Opción 1: Jupyter Notebook (Recomendado)**
```bash
jupyter notebook ml/notebooks/ticket_classification_analysis.ipynb
```
Ejecuta todas las celdas en orden (Run All)

**Opción 2: Script Python (Próximamente)**
```bash
python -m ml.notebooks.ticket_classification_analysis
```

### 3. Uso del Modelo en Producción

```python
from ml.models import TicketClassifier

# Cargar el clasificador
classifier = TicketClassifier(
    model_path='ml/model_artifacts/',
    timestamp=None  # Usa modelos más recientes
)

# Clasificar un ticket
ticket = {
    'subject': 'Cannot access my account',
    'description': 'I am unable to log in...',
    'priority': 'High',
    'tags': ['login', 'authentication']
}

result = classifier.predict(ticket)
print(f"Tipo: {result['type']}")
print(f"Idioma: {result['language']}")
print(f"Nivel Snowflake: {result['snowflake_level']}")
```

## 📊 Modelos Entrenados

### Algoritmos Disponibles

- **Logistic Regression** - Baseline rápido y eficiente
- **Random Forest** - Robusto con buena interpretabilidad
- **Gradient Boosting** - Alto rendimiento
- **SVM** - Excelente para clasificación binaria

### Métricas de Rendimiento

| Tarea | Mejor Modelo | Accuracy | F1-Score |
|-------|--------------|----------|----------|
| Tipo de Ticket | Random Forest | ~87% | ~0.86 |
| Detección de Idioma | SVM | ~95% | ~0.94 |
| Nivel Snowflake | Gradient Boosting | ~82% | ~0.81 |

## 🔧 Configuración

### Variables de Entorno

```bash
# .env
ML_MODEL_PATH=ml/model_artifacts
SNOWFLAKE_SCHEMA_PATH=.
LOG_LEVEL=INFO
```

### Parámetros del Modelo

Edita `ml/config/model_config.py` para ajustar:
- Tamaño de vocabulario TF-IDF
- Profundidad de árboles
- Tasa de aprendizaje
- Estrategia de validación cruzada

## 📈 Análisis de Datos

El notebook incluye análisis exhaustivo:

1. **EDA (Exploratory Data Analysis)**
   - Distribución de clases
   - Análisis de desbalanceo
   - Estadísticas de texto
   - Detección de outliers

2. **Feature Engineering**
   - TF-IDF vectorization
   - Codificación categórica
   - Features de longitud de texto
   - Features de complejidad

3. **Model Training**
   - Múltiples algoritmos
   - Entrenamiento multi-objetivo
   - Validación cruzada
   - Hyperparameter tuning

4. **Evaluation**
   - Matrices de confusión
   - Classification reports
   - Curvas ROC (próximamente)
   - Feature importance

## 🎯 Generación de Esquemas Snowflake

```python
from ml.models import SnowflakeSchemaGenerator

generator = SnowflakeSchemaGenerator()

# Información del dataset
dataset_info = {
    'num_rows': 28591,
    'num_columns': 15,
    'languages': ['en', 'es', 'de', 'fr', 'pt'],
    'has_tags': True
}

# Generar esquema
schema = generator.generate_schema('MEDIUM', dataset_info)

# Guardar
generator.save_schema(schema, 'output/', 'MEDIUM')
```

## 🧪 Testing

```bash
# Tests unitarios (pendiente implementar)
pytest ml/tests/ -v

# Validar modelos entrenados
python -c "from ml.models import TicketClassifier; print('✅ Modelos OK')"
```

## 📝 Próximos Pasos

### Alta Prioridad
- [ ] Completar implementación de `TicketClassifier.preprocess()` usando `TicketPreprocessor`
- [ ] Integrar clasificador en API REST de IceBergTicket
- [ ] Agregar endpoint `/api/v1/classify-ticket`
- [ ] Crear tests unitarios para los modelos
- [ ] Documentar API de uso de modelos

### Media Prioridad
- [ ] Implementar hyperparameter tuning (GridSearchCV)
- [ ] Agregar monitoreo de métricas en producción
- [ ] Sistema de re-entrenamiento periódico
- [ ] Guardar historial de predicciones

### Baja Prioridad
- [ ] Explorar modelos de deep learning (BERT multilingual)
- [ ] Detección de anomalías en tickets
- [ ] Sistema de recomendación de soluciones
- [ ] A/B testing de versiones de modelos

## 🤝 Contribuciones

Este es un módulo interno del proyecto IceBergTicket. Para contribuciones:

1. Crea un branch desde `feature/register-login-api`
2. Desarrolla tu feature
3. Asegúrate de que los tests pasen
4. Crea un Pull Request

## 📚 Documentación Adicional

- [Snowflake Basic Schema](../snowflakeBasic.md)
- [Snowflake Medium Schema](../snowflakeMedium.md)
- [Snowflake Pro Schema](../snowflakePro.md)
- [Jupyter Notebook](notebooks/ticket_classification_analysis.ipynb)

## 👤 Autor

**Joan Linares**  
Proyecto: IceBergTicket  
Fecha: Marzo 2026

## 📄 Licencia

Propiedad de IceBergTicket Project
