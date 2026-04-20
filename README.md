<div align="center">

<img src="src/web/img/IceBergTicket_Logo1.png" alt="IBTicket Logo" width="280"/>

# IBTicket

**Plataforma de gestión de tickets con Data Warehouse automático e IA**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat&logo=supabase&logoColor=white)](https://supabase.com)
[![Scikit-learn](https://img.shields.io/badge/Scikit--learn-ML-F7931E?style=flat&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)

</div>

---

## ¿Qué es IBTicket?

IBTicket es una plataforma web que convierte cualquier dataset de tickets en un **Data Warehouse estructurado con modelo estrella (Snowflake Schema)**, gestionado completamente en la nube. Sube un fichero de datos y la IA analiza su estructura, clasifica su complejidad y genera automáticamente las dimensiones, la tabla de hechos y las relaciones optimizadas para consultas analíticas.

Una vez creada la base de datos, puedes explorarla con SQL en el navegador, recibir nuevos tickets desde sistemas externos vía API autenticada y operar la cola completa desde la consola de operaciones.

---

## Flujo de la plataforma

```
Usuario                              Sistema
───────                              ───────

1. Login

2. Dashboard (lista de bases de datos)
       │
       ├── Crear BD ──→ Upload fichero ──→ IA analiza estructura
       │                                        │
       │                          ┌─────────────┴──────────────┐
       │                          │  3 modelos ML en pipeline  │
       │                          │  ─────────────────────────  │
       │                          │  Random Forest   → tipo     │
       │                          │  Naive Bayes     → idioma   │
       │                          │  Gradient Boost  → nivel DW │
       │                          └─────────────────────────────┘
       │                                        │
       │                          Genera Snowflake Schema
       │                          BASIC / MEDIUM / PRO
       │                                        │
       │                          Cifra (AES-256) y sube a Supabase
       │                                        │
       └── Explorar BD ←──────────────────────────────────────
               │
               ├── Visualizar schema (flowchart)
               ├── Ejecutar queries SQL
               ├── Añadir / editar registros
               ├── Generar y rotar API keys
               └── Salir → limpieza en memoria
```

---

## Niveles de Data Warehouse

La IA clasifica cada dataset en uno de tres niveles Snowflake, aplicando el esquema más adecuado:

| Nivel | Tablas incluidas | Uso típico |
|-------|-----------------|------------|
| **BASIC** | `fact_tickets`, `dim_status`, `dim_priority`, `dim_customer`, `dim_agent`, `dim_date`, `ticket_text` | Datasets simples, pocos campos |
| **MEDIUM** | BASIC + `dim_type`, `dim_language` | Datasets con categorías y soporte multiidioma |
| **PRO** | MEDIUM + `dim_queue`, `dim_tag`, `bridge_ticket_tags`, word counts | Datasets complejos con etiquetas y colas |

---

## Pipeline de Machine Learning

Tres modelos entrenados en paralelo sobre el mismo preprocesamiento TF-IDF:

| Modelo | Algoritmo | Predice |
|--------|-----------|---------|
| Clasificador de tipo | Random Forest | Categoría del ticket (8 tipos canónicos) |
| Detector de idioma | Naive Bayes | Idioma del texto (es, en, de, fr, pt…) |
| Selector de nivel DW | Gradient Boosting | Nivel Snowflake (BASIC / MEDIUM / PRO) |

Los artefactos entrenados viven en `ml/model_artifacts/` y son cargados en memoria por `MLService` (singleton) al arrancar la aplicación.

**Tipos de ticket soportados:**

- Acceso y Cuenta · Facturación y Pagos · Seguridad y Privacidad
- Error de Sistema / Rendimiento · Hardware y Red · Integración y Software
- Estrategia y Análisis · Otros

---

## Formatos de fichero soportados

| Formato | Extensiones |
|---------|-------------|
| CSV / TSV | `.csv`, `.tsv` |
| Excel | `.xlsx`, `.xls` |
| JSON / NDJSON | `.json`, `.jsonl`, `.ndjson` |
| Parquet | `.parquet` |
| SQLite | `.db`, `.sqlite`, `.sqlite3` |
| SQL dump | `.sql` |
| Texto plano | `.txt`, `.log` |

Tamaño máximo: **50 MB** por fichero.

---

## API REST

### Autenticación — `/api/v1/auth`

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/auth/register` | Registro de usuario |
| `POST` | `/auth/login` | Login → JWT access + refresh token |
| `POST` | `/auth/refresh` | Renovar access token |
| `POST` | `/auth/logout` | Invalidar sesión |

### Bases de datos — `/api/v1/files`

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/files/upload` | Subir fichero y generar DW |
| `GET` | `/files` | Listar mis bases de datos |
| `GET` | `/files/<id>` | Detalles de una BD |
| `DELETE` | `/files/<id>` | Eliminar BD |
| `POST` | `/files/<id>/share` | Generar código de acceso compartido |
| `POST` | `/files/join` | Unirse a una BD con código |
| `POST` | `/files/<id>/api-key` | Regenerar API key de ingest |

### Exploración SQL — `/api/v1/files/<id>`

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/tables` | Listar tablas del DW |
| `GET` | `/tables/<tabla>` | Datos de una tabla con paginación |
| `POST` | `/query` | Ejecutar query SQL libre |

### Ingest externo (autenticación por URL, sin JWT)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/ingest/<file_id>/<api_key>/tickets` | Crear uno o varios tickets |
| `PATCH` | `/ingest/<file_id>/<api_key>/tickets/<id>/status` | Actualizar estado de un ticket |

**Ejemplo — crear ticket desde sistema externo:**

```bash
curl -X POST https://tu-dominio.com/api/v1/ingest/18/tu_api_key/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "email": "usuario@empresa.com",
    "name": "Usuario",
    "body": "No puedo acceder a mi cuenta desde esta mañana.",
    "priority": "high"
  }'
```

**Ejemplo — actualizar estado:**

```bash
curl -X PATCH https://tu-dominio.com/api/v1/ingest/18/tu_api_key/tickets/42/status \
  -H "Content-Type: application/json" \
  -d '{"status": "resolved"}'
```

---

## Consola de operaciones (testWebAPI)

Interfaz web autónoma para operar la cola de tickets de una BD concreta. Diseñada para triage y resolución en tiempo real, con filtros avanzados, búsqueda con debounce y sincronización de estado en la URL.

```bash
python testWebAPI/app.py   # escucha en http://127.0.0.1:5055
```

**Parámetros de filtro de `/api/tickets`:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `q` | string | Búsqueda global (asunto, respuesta, email, ID) |
| `subject` | string | Filtro por asunto (LIKE) |
| `user` | string | Filtro por email o nombre de cliente |
| `status` | CSV | Estados separados por coma (`open,pending`) |
| `responded` | `yes`/`no` | Filtrar por si tiene respuesta |
| `date_from` | ISO date | Fecha de creación desde |
| `date_to` | ISO date | Fecha de creación hasta |
| `sort` | string | Campo de ordenación (`created_at`, `ticket_id`, `status`, `subject`, `responded`, `email`) |
| `order` | `asc`/`desc` | Dirección de ordenación |
| `page` | int | Página (desde 1) |
| `per_page` | int | Resultados por página (1–100) |

---

## Arquitectura

```
┌────────────────────────────────────────────────────────────────┐
│                     Portal web (Flask / Jinja2)                │
│         Login → Dashboard → Explorer (SQL, schema, keys)       │
└─────────────────────────┬──────────────────────────────────────┘
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
┌────────────────────────┐  ┌──────────────────────────────────┐
│   Pipeline ML          │  │   API REST  /api/v1              │
│   ─────────────────    │  │   ──────────────────────────     │
│   MLService (singleton)│  │   auth · files · db · ingest     │
│   TicketClassifier     │  │   saved_queries                  │
│   SnowflakeGenerator   │  └───────────────────┬──────────────┘
└────────────────────────┘                      │
                                                ▼
┌───────────────────────────────────────────────────────────────┐
│                         Supabase                              │
│   PostgreSQL                       Storage (blob)             │
│   ─────────                        ──────────────             │
│   users · files · user_files       BD SQLite cifradas         │
│   api_keys · saved_queries         (AES-256-GCM)              │
└───────────────────────────────────────────────────────────────┘
```

Las BDs SQLite nunca persisten en disco en el servidor: se descifran en memoria, se operan y al cerrar sesión se eliminan.

---

## Seguridad

| Capa | Mecanismo |
|------|-----------|
| Autenticación web | JWT con access token + refresh token |
| Datos en reposo | AES-256-GCM → Supabase Storage |
| API externa | API key por proyecto embebida en la URL |
| Contraseñas | Werkzeug `generate_password_hash` (bcrypt) |
| Transporte | HTTPS (producción con Gunicorn + proxy inverso) |

---

## Instalación local

### Con `uv` (recomendado)

```bash
git clone https://github.com/JoanLinares/IceBergTicket.git
cd IceBergTicket

pip install uv
uv sync

cp .env.example .env
# Editar .env con las credenciales de Supabase y el JWT_SECRET
```

### Con `pip`

```bash
git clone https://github.com/JoanLinares/IceBergTicket.git
cd IceBergTicket

python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows

pip install -e .

cp .env.example .env
# Editar .env con las credenciales de Supabase y el JWT_SECRET
```

### Arrancar

```bash
# API principal (puerto 5000)
python app.py

# Consola de operaciones (puerto 5055, terminal separada)
python testWebAPI/app.py
```

### Con Docker

```bash
docker compose up --build
```

---

## Variables de entorno

Copia `.env.example` a `.env` y rellena los valores necesarios:

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `DATABASE_URL` | Sí | Cadena de conexión Supabase PostgreSQL |
| `JWT_SECRET` | Sí | Secreto para firmar los tokens JWT |
| `SECRET_KEY` | Sí | Secreto de sesión Flask |
| `ML_ARTIFACTS_DIR` | No | Ruta a los `.pkl` entrenados (por defecto `ml/model_artifacts`) |
| `TESTWEB_INGEST_BASE_URL` | No | URL base del ingest para la consola de operaciones |
| `TESTWEB_PORT` | No | Puerto de la consola (por defecto `5055`) |

---

## Estructura del proyecto

```
IceBergTicket/
├── app.py                       # Entry point Flask (API + portal web)
├── pyproject.toml               # Dependencias (uv / pip install -e .)
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── src/
│   ├── api/
│   │   ├── routers/             # Blueprints Flask por dominio
│   │   ├── controllers/         # Lógica de cada endpoint
│   │   ├── models/              # Acceso a PostgreSQL (Supabase)
│   │   └── middlewares/         # JWT middleware
│   │
│   ├── web/
│   │   ├── routers/             # Rutas del portal web
│   │   ├── templates/           # HTML Jinja2 (login, dashboard, explorer)
│   │   └── static/              # CSS e imágenes
│   │
│   └── services/
│       ├── ml_service.py        # Singleton MLService
│       ├── dw_service.py        # Generación Snowflake Schema en SQLite
│       ├── import_service.py    # Parser de ficheros (CSV, Excel, JSON…)
│       ├── file_service.py      # Cifrado AES-256-GCM + Supabase Storage
│       ├── auth_service.py      # Registro, login, hashing
│       ├── JWT_service.py       # Creación y validación de tokens
│       └── db_session_service.py
│
├── ml/
│   ├── models/
│   │   ├── ticket_classifier.py     # TicketClassifier (3 modelos en paralelo)
│   │   ├── snowflake_generator.py   # Generador de DDL Snowflake
│   │   └── preprocessor.py         # Preprocesamiento TF-IDF
│   ├── model_artifacts/             # .pkl entrenados (excluidos de git)
│   ├── notebooks/                   # Análisis y entrenamiento Jupyter
│   └── config/
│       └── model_config.py
│
├── testWebAPI/                  # Consola de operaciones
│   ├── app.py                   # Flask proxy + filtros server-side
│   ├── templates/index.html
│   └── static/
│       ├── styles.css
│       └── app.js
│
└── generate_large_dataset.py    # Generador de datasets sintéticos
```

---

## Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.10+ · Flask 3 |
| Frontend | Jinja2 · HTML / CSS / JS vanilla |
| Base de datos | Supabase (PostgreSQL + Storage) |
| Data Warehouse | SQLite en memoria (Snowflake Schema) |
| ML / IA | Pandas · Scikit-learn · TF-IDF |
| Seguridad | Cryptography (AES-256-GCM) · PyJWT |
| Despliegue | Docker · Gunicorn |
| Gestión de deps | uv · pyproject.toml |

---

## Licencia

Proyecto Final de Curso — 2026

<div align="center">

Desarrollado por [Joan Linares](https://github.com/JoanLinares) y [Albert Garrido](https://github.com/albertgarrido4)

</div>
