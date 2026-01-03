<div align="center">

<img src="src/web/img/IceBergTicket_Logo1.png" alt="IBTicket Logo" width="300"/>

# 🧊 IBTicket

**I**ntelligència **A**rtificial · **B**ig **D**ata · **Ice**berg · **Ticket**s

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Snowflake](https://img.shields.io/badge/Snowflake-Data%20Warehouse-29B5E8?style=flat&logo=snowflake&logoColor=white)](https://snowflake.com)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat&logo=supabase&logoColor=white)](https://supabase.com)

</div>

---

## 📋 Què és IBTicket?

**IBTicket** és una plataforma web que permet crear **sistemes de gestió de tickets** amb un **data warehouse** automatitzat. Puja un fitxer de dades i la IA genera automàticament una base de dades analítica en model estrella (Snowflake).

### 🎯 Problema que resol

Les empreses tenen dades de tickets en formats diversos (CSV, Excel, bases de dades) i necessiten:
- Centralitzar-les en un data warehouse
- Analitzar-les fàcilment (per categoria, àrea, temps...)
- Integrar nous tickets des de sistemes externs
- Alliberar càrrega de la base de dades operativa

---

## ✨ Funcionalitats

| Funcionalitat | Descripció |
|---------------|------------|
| 📤 **Upload de dades** | Suporta CSV, Parquet, JSON, SQLite |
| 🤖 **Interpretació amb IA** | Detecta estructura, columnes, relacions |
| ⭐ **Model estrella automàtic** | Genera dimensions, fets, àrees funcionals |
| 🔐 **Dades xifrades** | Emmagatzematge segur a Supabase |
| 🔗 **API REST** | Connection strings per integrar amb altres sistemes |
| 📊 **Visualització** | Flowchart del schema generat |

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                         PORTAL WEB                              │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │  Login   │ →  │   Dashboard  │ →  │   Gestió Projectes    │  │
│  │ (cookies)│    │  (projectes) │    │ (upload, schema, API) │  │
│  └──────────┘    └──────────────┘    └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                      PROCESSAMENT                              │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │ Parser       │ →  │ IA Inferència│ →  │ Generador       │   │
│  │ (CSV,JSON..) │    │ (estructura) │    │ Schema Snowflake│   │
│  └──────────────┘    └──────────────┘    └─────────────────┘   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                     EMMAGATZEMATGE                             │
│  ┌─────────────────────┐         ┌─────────────────────────┐   │
│  │     SUPABASE        │         │       SNOWFLAKE         │   │
│  │  ─────────────────  │         │  ───────────────────    │   │
│  │  • Usuaris          │         │  • Model estrella       │   │
│  │  • Projectes        │         │  • Dimensions           │   │
│  │  • Dades xifrades   │         │  • Taula de fets        │   │
│  │  • API Keys         │         │  • Consultes analítiques│   │
│  └─────────────────────┘         └─────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API EXTERNA                                │
│         POST/PUT /api/v1/tickets/{api_key}                      │
│         → IA classifica → Insereix a dimensió correcta          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Instal·lació

```bash
# Clonar repositori
git clone https://github.com/JoanLinares/IceBergTicket.git
cd IceBergTicket

# Crear entorn virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instal·lar dependències
pip install -r requirements.txt

# Configurar variables d'entorn
cp .env.example .env
# Editar .env amb les teves credencials

# Executar
python app.py
```

---

## 📁 Estructura del Projecte

```
IBTicket/
├── app.py                 # Entry point Flask
├── requirements.txt       # Dependències Python
├── docker-compose.yml     # Contenidors
├── Dockerfile
│
├── src/                   # Codi de l'aplicació
│   ├── api/               # REST API (/api/v1)
│   │   ├── routers/       # Endpoints
│   │   ├── controllers/   # Lògica dels endpoints
│   │   ├── middlewares/   # Auth, validació
│   │   └── models/        # Schemas request/response
│   │
│   ├── web/               # Portal web (HTML)
│   │   ├── routers/       # Rutes web
│   │   ├── templates/     # HTML (Jinja2)
│   │   ├── static/        # CSS, imatges
│   │   └── middlewares/   # Sessions, cookies
│   │
│   ├── services/          # Lògica de negoci
│   └── models/            # Models de dades
│
└── ml/                    # Machine Learning
    ├── training/          # Scripts d'entrenament
    ├── model_artifacts/   # Models entrenats
    ├── notebooks/         # Jupyter notebooks
    ├── data/              # Dades (raw/processed)
    ├── evaluation/        # Mètriques, avaluació
    └── config/            # Configuració ML
```

---

## 🔧 Stack Tecnològic

| Capa | Tecnologia |
|------|------------|
| **Backend** | Python 3.10+ · Flask |
| **Frontend** | HTML · CSS (server-side rendering) |
| **Base de dades** | Supabase (PostgreSQL) |
| **Data Warehouse** | Snowflake |
| **ML/IA** | Pandas · Scikit-learn |
| **Seguretat** | Cryptography (xifrat AES) |
| **Desplegament** | Docker · Gunicorn |

---

## 🔐 Seguretat

- **Autenticació**: Cookies amb TTL configurable
- **Xifrat en repòs**: Dades dels projectes xifrades amb AES-256
- **API Keys**: Tokens únics per cada projecte
- **CORS**: Configurat per a peticions controlades

---

## 📈 Exemples de Consultes Analítiques

Un cop generat el model estrella, pots obtenir fàcilment:

```sql
-- Tickets per categoria l'any 2024
SELECT categoria, COUNT(*) 
FROM fact_tickets 
JOIN dim_temps ON ... 
WHERE any = 2024 
GROUP BY categoria;

-- Evolució mensual d'incidències
SELECT mes, COUNT(*) 
FROM fact_tickets 
JOIN dim_temps ON ... 
GROUP BY mes;

-- Mètriques de resolució per àrea
SELECT area, AVG(temps_resolucio), COUNT(*) 
FROM fact_tickets 
JOIN dim_area ON ... 
GROUP BY area;
```

---

## 🎨 Branding

**IBTicket** = **I**ce**B**erg**Ticket**

| Element | Significat |
|---------|------------|
| **I** | **AI** (Intel·ligència Artificial) |
| **B** | **Big Data** |
| **Iceberg** | Snowflake (fred) + Profunditat de dades |
| **Ticket** | Gestió de tickets |
| 🚢 | La "nube del mar" - Cloud computing marítim |
| ❄️ | Snowflake - Data warehouse |

---

## 📄 Llicència

Projecte de pràctiques - 2026

---

<div align="center">

**Desenvolupat amb ❄️ per [Joan Linares](https://github.com/JoanLinares)**

</div>
