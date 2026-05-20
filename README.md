<div align="center">

<img src="src/web/img/IceBergTicket_Logo1.png" alt="IceBergTicket logo" width="280"/>

# IceBergTicket

Plataforma Flask para convertir datasets de tickets en bases SQLite analiticas, cifradas y consultables desde un portal web o una API REST.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-Data%20Warehouse-003B57?style=flat&logo=sqlite&logoColor=white)](https://sqlite.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Metadata%20%2B%20Blobs-4169E1?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Scikit-learn](https://img.shields.io/badge/Scikit--learn-ML-F7931E?style=flat&logo=scikitlearn&logoColor=white)](https://scikit-learn.org)

</div>

---

## Descripcion General

**IceBergTicket** recibe archivos con tickets de soporte, normaliza sus columnas, enriquece cada fila con modelos de machine learning y genera una base de datos SQLite con un esquema analitico de tipo estrella/snowflake.

El resultado no se guarda como archivo plano sin proteccion: la base se comprime, se cifra con AES-256-GCM y se almacena como blob en PostgreSQL. La aplicacion mantiene metadatos, permisos, claves de integracion y consultas guardadas en tablas relacionales.

El proyecto tiene dos superficies principales:

- **Portal web**: login, dashboard de bases de datos, carga de archivos, explorador de tablas, ejecucion de SQL, queries guardadas, compartir bases, regenerar API keys y actualizar de nivel.
- **API REST**: autenticacion JWT, subida/listado de bases, consulta de tablas, ejecucion SQL, queries guardadas e ingest externa de tickets mediante API key.

---

## Flujo Principal

```text
Usuario / API
    |
    | 1. Sube CSV, TSV, JSON, JSONL, TXT, LOG, Parquet, Excel, SQLite o SQL
    v
ImportService
    |
    | 2. Normaliza columnas y garantiza subject/body
    v
MLService
    |
    | 3. Predice tipo, idioma y nivel sugerido por ticket
    v
DWService
    |
    | 4. Elige el esquema minimo para los campos soportados detectados
    |    BASIC, MEDIUM o PRO
    v
SQLite DW en memoria
    |
    | 5. Inserta dimensiones, fact_tickets y ticket_text
    v
Compresion + cifrado AES-256-GCM
    |
    | 6. Guarda blob cifrado y metadatos en PostgreSQL
    v
Dashboard / Explorer / API de ingest
```

Importante: aunque el sistema predice `pred_level` con ML, la eleccion operativa del esquema final la hace `DWService` con una regla conservadora basada en las columnas presentes y soportadas por el DW.

---

## Niveles de Data Warehouse

IceBergTicket genera **una sola base SQLite por carga**. El nivel se decide por el minimo esquema capaz de almacenar los campos soportados que se detectan en el dataset:

| Nivel | Cuando se usa | Diferencia principal |
| --- | --- | --- |
| **BASIC** | Dataset sin columnas explicitas de idioma/tipo y sin campos avanzados | Dimensiones esenciales, `pred_type` y `pred_language` en `fact_tickets` |
| **MEDIUM** | Dataset con `ticket_type` o `language` | Añade `dim_type` y `dim_language` |
| **PRO** | Dataset con `queue`, `answer`, `version`, `tags` o columnas `tag_*` | Añade colas, tags, puente many-to-many, respuesta y metricas de texto |

Nota: `version` actua actualmente como señal para subir a PRO, pero el esquema PRO no tiene una columna dedicada para persistir versiones.

Referencias exactas de cada esquema:

- [snowflakeBasic.md](snowflakeBasic.md)
- [snowflakeMedium.md](snowflakeMedium.md)
- [snowflakePro.md](snowflakePro.md)

---

## Modelos de Machine Learning

Los modelos de produccion se cargan desde `ml/model_artifacts/` mediante `src/services/ml_service.py`.

| Tarea | Artefacto | Algoritmo real cargado | Features | Rendimiento test |
| --- | --- | --- | --- | --- |
| Tipo de ticket | `model_type_random_forest.pkl` | `LinearSVC` | TF-IDF especifico (`tfidf_vectorizer_type.pkl`) | Accuracy 0.9477, F1 0.9478 |
| Idioma | `model_language_naive_bayes.pkl` | `GaussianNB` | Features combinadas escaladas | Accuracy 1.0000, F1 1.0000 |
| Nivel Snowflake sugerido | `model_snowflake_gradient_boosting.pkl` | `GradientBoostingClassifier` | Features combinadas escaladas | Accuracy 0.8159, F1 0.7989 |

Notas importantes:

- El archivo `model_type_random_forest.pkl` mantiene ese nombre por compatibilidad historica, pero el artefacto actual contiene un `LinearSVC`.
- La deteccion de idioma no depende solo del modelo: `MLService` combina la prediccion con normalizacion de codigos, heuristicas por texto y `langdetect` cuando esta disponible.
- Durante ingest externa, el tipo de ticket se normaliza a un catalogo de negocio de 8 categorias: `Estrategia y Analisis`, `Hardware y Red`, `Otros`, `Seguridad y Privacidad`, `Error de Sistema / Rendimiento`, `Facturacion y Pagos`, `Acceso y Cuenta`, `Integracion y Software`.
- La prediccion `pred_level` queda como enriquecimiento, pero el esquema final se decide por columnas reales para preservar datos.

El entrenamiento y la evaluacion estan documentados en `ml/notebooks/ticket_classification_analysis.ipynb`; la metadata activa esta en `ml/model_artifacts/model_metadata.pkl`.

---

## API REST

Todas las rutas de API estan bajo `/api/v1`.

### Autenticacion

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| `POST` | `/auth/register` | Crea usuario y devuelve access/refresh token |
| `POST` | `/auth/login` | Login con email y password |
| `POST` | `/auth/refresh` | Rota refresh token y devuelve nuevo access token |
| `POST` | `/auth/logout` | Invalida el refresh token del usuario |

### Bases de Datos

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| `POST` | `/files/upload` | Sube dataset, clasifica tickets y crea el SQLite DW |
| `GET` | `/files` | Lista bases propias y compartidas |
| `GET` | `/files/<file_id>` | Detalle de una base accesible |
| `DELETE` | `/files/<file_id>` | Elimina una base propia |
| `POST` | `/files/<file_id>/share` | Genera o regenera codigo de invitacion |
| `POST` | `/files/join` | Une al usuario a una base mediante codigo |
| `POST` | `/files/<file_id>/api-key` | Regenera la API key de ingest |

### Exploracion y SQL

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| `GET` | `/files/<file_id>/tables` | Lista tablas/vistas y numero de filas |
| `GET` | `/files/<file_id>/tables/<table_name>` | Devuelve datos paginados |
| `POST` | `/files/<file_id>/query` | Ejecuta SQL sobre el SQLite |
| `GET` | `/files/<file_id>/queries` | Lista queries guardadas |
| `POST` | `/files/<file_id>/queries` | Guarda una query |
| `GET` | `/files/<file_id>/queries/<query_id>` | Obtiene una query guardada |
| `PATCH` | `/files/<file_id>/queries/<query_id>` | Actualiza nombre o SQL |
| `DELETE` | `/files/<file_id>/queries/<query_id>` | Elimina una query |

Las consultas `SELECT` devuelven hasta 1.000 filas. Las operaciones de escritura (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, etc.) se ejecutan sobre el SQLite temporal y despues se vuelve a comprimir, cifrar y subir el blob.

Por seguridad, `ATTACH` y `DETACH` estan bloqueados.

### Ingest Externa

La ingest no usa JWT. Se autentica con la API key propia de cada base:

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| `POST` | `/ingest/<file_id>/<api_key>/tickets` | Inserta uno o varios tickets nuevos |
| `PATCH` | `/ingest/<file_id>/<api_key>/tickets/<ticket_id>/status` | Actualiza el estado de un ticket |

Ejemplo:

```bash
curl -X POST "http://localhost:5000/api/v1/ingest/12/API_KEY/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "No puedo acceder a mi cuenta",
    "body": "El login falla despues de cambiar la contrasena",
    "priority": "high",
    "email": "cliente@example.com"
  }'
```

---

## Seguridad y Persistencia

| Capa | Implementacion actual |
| --- | --- |
| Web | Sesion Flask para portal |
| API | JWT access token + refresh token hasheado |
| Ingest externa | API key por base, almacenada como hash |
| Cifrado | AES-256-GCM con nonce por escritura |
| Integridad | SHA-256 del payload comprimido antes de cifrar |
| Almacenamiento | Blob cifrado en `public.file_storage_blobs` |
| Metadatos | PostgreSQL: `users`, `files`, `user_files`, `saved_queries` |
| SQL seguro | `ATTACH`/`DETACH` bloqueados, limite de filas en SELECT |

Formato de compresion:

- Creacion inicial: prefijo `LMDB` con LZMA.
- Reescrituras frecuentes por ingest: prefijo `ZLDB` con zlib.
- Lectura: `decompress_db` soporta `LMDB`, `ZLDB` y SQLite raw por compatibilidad.

---

## Instalacion Local

Requisitos:

- Python 3.10 o superior.
- `uv` para sincronizar dependencias.
- PostgreSQL/Supabase accesible mediante `DATABASE_URL`.
- Artefactos ML en `ml/model_artifacts/`.

Instalacion:

```bash
uv sync
```

Variables de entorno recomendadas:

```bash
DATABASE_URL=postgresql://postgres:password@host:5432/postgres
MASTER_KEY_V1=<base64-de-32-bytes>
SECRET_KEY=<clave-flask>
JWT_SECRET=<clave-jwt>
PORT=5000
ML_ARTIFACTS_DIR=ml/model_artifacts
```

Generar `MASTER_KEY_V1`:

```bash
uv run python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Arrancar la aplicacion:

```bash
uv run python app.py
```

La app quedara disponible en:

```text
http://localhost:5000
```

---

## Estructura del Proyecto

```text
IceBergTicket/
|-- app.py                         # Entry point Flask principal
|-- pyproject.toml                 # Dependencias y configuracion Python
|-- uv.lock                        # Lockfile de dependencias
|-- snowflakeBasic.md              # Esquema BASIC real
|-- snowflakeMedium.md             # Esquema MEDIUM real
|-- snowflakePro.md                # Esquema PRO real
|
|-- src/
|   |-- api/
|   |   |-- routers/               # Registro de rutas /api/v1
|   |   |-- controllers/           # Logica HTTP
|   |   |-- middlewares/           # JWT y validaciones
|   |   `-- models/                # Acceso a tablas PostgreSQL
|   |
|   |-- services/
|   |   |-- import_service.py      # Parser multi-formato
|   |   |-- ml_service.py          # Carga e inferencia de modelos
|   |   |-- dw_service.py          # Generacion de SQLite DW
|   |   |-- file_service.py        # Cifrado y blobs
|   |   `-- db_session_service.py  # Lectura/escritura SQL sobre SQLite cifrado
|   |
|   `-- web/
|       |-- routers/               # Portal web
|       |-- templates/             # Jinja2
|       `-- static/                # CSS, JS e imagenes
|
|-- ml/
|   |-- config/model_config.py
|   |-- data/
|   |-- model_artifacts/           # Modelos .pkl activos
|   |-- models/                    # Wrappers ML historicos
|   `-- notebooks/                 # Entrenamiento y evaluacion
|
`-- testWebAPI/                    # Prototipo/API de pruebas separada
```

---

## Herramienta de Pruebas

`testWebAPI/` es una aplicacion Flask auxiliar para probar la ingest externa y consultar una base concreta usando su `file_id` y `api_key`. No se registra dentro de la app principal.

Se configura con:

```bash
TESTWEB_INGEST_BASE_URL=http://127.0.0.1:5000/api/v1/ingest/<file_id>/<api_key>
```

Tambien incluye `testWebAPI/consulta.sql` con ejemplos exploratorios de consulta directa.

---

## Formatos de Entrada Soportados

`ImportService` acepta:

```text
.csv, .tsv, .json, .jsonl, .ndjson, .txt, .log,
.parquet, .xlsx, .xls, .db, .sqlite, .sqlite3, .sql
```

Si el archivo no trae `subject` y `body`, el parser intenta derivarlos a partir de columnas textuales. Si no encuentra texto, crea columnas minimas para que el pipeline ML pueda procesar el dataset.

Aliases reconocidos:

| Campo interno | Aliases |
| --- | --- |
| `subject` | `subject`, `title`, `summary`, `asunto` |
| `body` | `body`, `description`, `message`, `text`, `content`, `descripcion`, `mensaje` |
| `priority` | `priority`, `prioridad` |
| `queue` | `queue`, `department`, `category`, `departamento` |
| `language` | `language`, `lang`, `idioma` |
| `created_at` | `created_at`, `created`, `date`, `timestamp`, `fecha` |

---

## Consultas de Ejemplo

Tickets por prioridad:

```sql
SELECT p.priority_name, COUNT(*) AS total
FROM fact_tickets f
JOIN dim_priority p ON p.priority_key = f.priority_key
GROUP BY p.priority_name
ORDER BY total DESC;
```

Tickets por idioma en MEDIUM/PRO:

```sql
SELECT l.language_code, l.language_name, COUNT(*) AS total
FROM fact_tickets f
JOIN dim_language l ON l.language_key = f.language_key
GROUP BY l.language_code, l.language_name
ORDER BY total DESC;
```

Tags mas frecuentes en PRO:

```sql
SELECT t.tag_name, COUNT(*) AS total
FROM bridge_ticket_tags b
JOIN dim_tag t ON t.tag_key = b.tag_key
GROUP BY t.tag_name
ORDER BY total DESC;
```

---

## Estado del Proyecto

El proyecto esta orientado a entorno academico/prototipo funcional:

- La app principal esta en `app.py` y registra `src.api.routers` y `src.web.routers`.
- El DW generado es SQLite comprimido y cifrado, no una conexion directa a Snowflake Cloud.
- `testWebAPI/` contiene una API de pruebas independiente y no forma parte del flujo principal.
- La documentacion de esquemas se mantiene alineada con `src/services/dw_service.py`.

---

## Licencia

Proyecto Final de Curso, 2026.

<div align="center">

Desarrollado por Joan Linares.

</div>
