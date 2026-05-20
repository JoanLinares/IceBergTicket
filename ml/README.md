# IceBergTicket ML

Modulo de entrenamiento e inferencia para clasificar tickets y enriquecer los datasets antes de generar las bases analiticas SQLite.

Este directorio contiene el codigo, el notebook y los datasets necesarios para reproducir el entrenamiento. Los modelos entrenados no se publican en el repositorio: se generan localmente al ejecutar el notebook y quedan en `ml/model_artifacts/`.

---

## Objetivo

El pipeline ML cubre tres tareas:

| Tarea | Salida | Uso en IceBergTicket |
| --- | --- | --- |
| Tipo de ticket | `pred_type` | Clasificacion funcional del ticket y dimensiones de tipo |
| Idioma | `pred_language` | Normalizacion de idioma y `dim_language` |
| Nivel DW sugerido | `pred_level` | Indicador auxiliar para BASIC, MEDIUM o PRO |

La decision final del esquema no depende solo del modelo. `DWService` revisa las columnas reales del archivo y elige el nivel minimo que soporta la informacion disponible.

---

## Dataset

El entrenamiento se basa en el dataset publico:

[Customer IT Support - Ticket Dataset](https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets)

| Campo | Valor |
| --- | --- |
| Autor | Tobias Bueck |
| Plataforma | Kaggle |
| Licencia | Attribution 4.0 International (CC BY 4.0) |
| Usability | 10.00 |
| Frecuencia esperada de actualizacion | Quarterly |
| Tags | Text, Intermediate, English, Multiclass Classification, Neural Networks |

Gracias al autor por publicar un dataset etiquetado de tickets de soporte con asunto, cuerpo, respuesta, prioridad, cola, idioma, tipo y tags. Esa estructura permite entrenar modelos de clasificacion y, a la vez, validar los tres niveles de data warehouse del proyecto.

---

## Estructura

```text
ml/
|-- config/
|   `-- model_config.py             # Configuracion de features, modelos y rutas
|
|-- data/                           # CSV usados para entrenamiento y pruebas
|   |-- aa_dataset-tickets-multi-lang-5-2-50-version.csv
|   |-- dataset-tickets-multi-lang-4-20k.csv
|   |-- dataset-tickets-multi-lang3-4k.csv
|   `-- dataset-tickets-german_normalized*.csv
|
|-- data/processed/                 # Splits o datasets derivados
|
|-- model_artifacts/                # Generado al entrenar, no versionado
|
|-- models/
|   |-- preprocessor.py             # Transformacion de tickets a features
|   |-- ticket_classifier.py        # Wrapper de inferencia
|   `-- snowflake_generator.py      # Generador documental de esquemas
|
`-- notebooks/
    `-- ticket_classification_analysis.ipynb
```

`*.pkl` y `*.joblib` estan excluidos por `.gitignore`, asi que despues de entrenar apareceran solo en la copia local.

---

## Entrenamiento

Instalar dependencias desde la raiz del proyecto:

```bash
uv sync
```

Abrir el notebook:

```bash
uv run jupyter notebook ml/notebooks/ticket_classification_analysis.ipynb
```

Ejecutar todas las celdas en orden. Al finalizar, el notebook genera los artefactos necesarios en:

```text
ml/model_artifacts/
```

La app principal los carga automaticamente desde esa ruta, o desde la ruta indicada en `ML_ARTIFACTS_DIR`.

---

## Inferencia

En produccion, `src/services/ml_service.py` carga los artefactos entrenados y aplica el mismo preprocesado a archivos subidos o tickets recibidos por ingest externa.

Flujo resumido:

```text
archivo o payload JSON
    -> normalizacion de columnas
    -> features de texto y categorias
    -> pred_type, pred_language, pred_level
    -> generacion o actualizacion del SQLite DW
```

La deteccion de idioma combina prediccion supervisada, normalizacion de codigos, heuristicas por texto y `langdetect` cuando esta disponible.

---

## Variables Relacionadas

```bash
ML_ARTIFACTS_DIR=ml/model_artifacts
```

Si no se define, la aplicacion usa por defecto `ml/model_artifacts/`.

---

## Notas de Licencia

El dataset externo esta publicado bajo CC BY 4.0, por lo que cualquier uso publico debe mantener atribucion al autor y a la fuente original. Este proyecto lo cita en la documentacion y lo usa con finalidad academica.
