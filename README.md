<div align="center">

<img src="src/web/img/IceBergTicket_Logo1.png" alt="IBTicket Logo" width="300"/>

# 🧊 IBTicket

**I**ntel·ligència **A**rtificial · **B**ig **D**ata · **Ice**berg · **Ticket**s

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Snowflake](https://img.shields.io/badge/Snowflake_Schema-Data%20Warehouse-29B5E8?style=flat&logo=snowflake&logoColor=white)](#)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat&logo=supabase&logoColor=white)](https://supabase.com)

</div>

---

## 📋 Què és IBTicket?

**IBTicket** és una plataforma web que permet crear **sistemes de gestió de tickets** amb bases de dades estructurades automàticament. Puja un fitxer de dades i la **IA interpreta l'estructura** per generar una base de dades amb **model estrella (Snowflake schema)** — dimensions, fets i relacions optimitzades per a consultes analítiques.

### 🎯 Problema que resol

Les empreses tenen dades de tickets en formats diversos (CSV, Excel, bases de dades) i necessiten:
- Estructurar-les en un model analític sense feina manual
- Analitzar-les fàcilment (per categoria, àrea, temps...)
- Integrar nous tickets des de sistemes externs via API
- Visualitzar l'estructura i fer consultes des de la plataforma

---

## 🔄 Flux de la Plataforma

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           FLUX COMPLET                                     │
└────────────────────────────────────────────────────────────────────────────┘

   👤 USUARI                           🤖 SISTEMA
   ────────                           ──────────

   1. Login al portal
         │
         ▼
   2. Dashboard amb llista de BD
         │
         ├──→ Crear nova BD ─────────→ 3. Upload fitxer (CSV, JSON, 
         │                                  Parquet, SQLite)
         │                                       │
         │                                       ▼
         │                              4. IA analitza estructura:
         │                                 • Detecta columnes
         │                                 • Identifica tipus de dades
         │                                 • Troba relacions
         │                                 • Classifica dimensions/fets
         │                                       │
         │                                       ▼
         │                              5. Genera BD amb model estrella:
         │                                 ┌─────────────────────┐
         │                                 │     SNOWFLAKE       │
         │                                 │      SCHEMA         │
         │                                 ├─────────────────────┤
         │                                 │ dim_categoria       │
         │                                 │ dim_area            │
         │                                 │ dim_temps           │
         │                                 │ dim_prioritat       │
         │                                 │ fact_tickets        │
         │                                 └─────────────────────┘
         │                                       │
         │                                       ▼
         │                              6. Xifra i guarda a Supabase Storage
         │                                       │
         ▼                                       │
   7. Entra a una BD ←──────────────────────────-┘
         │
         ▼
   8. Sistema descarrega i descifra en memòria
         │
         ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                    ENTORN DE TREBALL                        │
   │  ┌─────────────────────────────────────────────────────┐    │
   │  │  📊 Visualitza schema (flowchart dimensions/fets)   │    │
   │  │  🔍 Executa queries SQL sobre les dades             │    │
   │  │  ➕ Afegeix nous registres                          │    │
   │  │  ✏️  Edita dades existents                          │    │
   │  │  🔗 Obté API Keys per integració externa            │    │
   │  │  💾 Guarda canvis (xifra i puja)                    │    │
   │  └─────────────────────────────────────────────────────┘    │
   └─────────────────────────────────────────────────────────────┘
         │
         ▼
   9. Sortir → neteja memòria
```

---

## 🔗 Integració amb Serveis Externs

Cada base de dades té **API Keys úniques** que permeten a sistemes externs enviar nous tickets:

```
┌─────────────────────┐         ┌─────────────────────────────────┐
│   SISTEMA EXTERN    │         │         IBTICKET API            │
│  (CRM, ERP, Web...) │         │                                 │
├─────────────────────┤         ├─────────────────────────────────┤
│                     │  POST   │                                 │
│  Nou ticket ───────────────────→ /api/v1/tickets/{api_key}      │
│                     │         │         │                       │
│                     │         │         ▼                       │
│                     │         │  IA classifica el ticket        │
│                     │         │  (determina dimensió correcta)  │
│                     │         │         │                       │
│                     │         │         ▼                       │
│                     │         │  Insereix a la BD corresponent  │
│                     │         │                                 │
│                     │   GET   │                                 │
│  Consulta estat ───────────────→ /api/v1/tickets/{api_key}/{id} │
│                     │         │                                 │
│                     │   PUT   │                                 │
│  Actualitza ───────────────────→ /api/v1/tickets/{api_key}/{id} │
│                     │         │                                 │
└─────────────────────┘         └─────────────────────────────────┘
```

**Exemple d'integració:**
```bash
# Crear nou ticket des de sistema extern
curl -X POST https://ibticket.app/api/v1/tickets/sk_abc123 \
  -H "Content-Type: application/json" \
  -d '{"title": "Error login", "description": "...", "priority": "alta"}'

# Consultar ticket
curl https://ibticket.app/api/v1/tickets/sk_abc123/42

# Actualitzar estat
curl -X PUT https://ibticket.app/api/v1/tickets/sk_abc123/42 \
  -d '{"status": "resolt"}'
```

---

## ⭐ Model Estrella (Snowflake Schema)

La IA genera automàticament una estructura optimitzada per a consultes analítiques:

```
                    ┌─────────────────┐
                    │  dim_categoria  │
                    │─────────────────│
                    │ id              │
                    │ nom             │
                    │ descripcio      │
                    └────────┬────────┘
                             │
┌─────────────────┐          │          ┌─────────────────┐
│    dim_area     │          │          │   dim_temps     │
│─────────────────│          │          │─────────────────│
│ id              │          │          │ id              │
│ nom             │          │          │ data            │
│ responsable     │          │          │ dia, mes, any   │
└────────┬────────┘          │          │ trimestre       │
         │                   │          └────────┬────────┘
         │     ┌─────────────┴───────────────┐   │
         │     │        fact_tickets         │   │
         │     │─────────────────────────────│   │
         └────→│ id                          │←──┘
               │ categoria_id (FK)           │
               │ area_id (FK)                │
               │ temps_id (FK)               │
               │ prioritat_id (FK)           │
               │ titol                       │
               │ descripcio                  │
               │ temps_resolucio             │
               │ estat                       │
               └─────────────┬───────────────┘
                             │
                    ┌────────┴────────┐
                    │ dim_prioritat   │
                    │─────────────────│
                    │ id              │
                    │ nivell          │
                    │ sla_hores       │
                    └─────────────────┘
```

---

## 🔍 Queries des de la Plataforma

Un cop dins d'una BD, pots executar consultes SQL directament:

```sql
-- Tickets per categoria l'any 2025
SELECT c.nom as categoria, COUNT(*) as total
FROM fact_tickets t
JOIN dim_categoria c ON t.categoria_id = c.id
JOIN dim_temps d ON t.temps_id = d.id
WHERE d.any = 2025
GROUP BY c.nom
ORDER BY total DESC;

-- Temps mitjà de resolució per àrea
SELECT a.nom as area, AVG(t.temps_resolucio) as mitjana_hores
FROM fact_tickets t
JOIN dim_area a ON t.area_id = a.id
WHERE t.estat = 'resolt'
GROUP BY a.nom;

-- Evolució mensual d'incidències
SELECT d.mes, d.any, COUNT(*) as tickets
FROM fact_tickets t
JOIN dim_temps d ON t.temps_id = d.id
GROUP BY d.any, d.mes
ORDER BY d.any, d.mes;
```

---

## 🏗️ Arquitectura Tècnica

```
┌─────────────────────────────────────────────────────────────────┐
│                         PORTAL WEB                               │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │  Login   │ →  │   Dashboard  │ →  │   Entorn de Treball   │  │
│  │ (cookies)│    │  (llista BD) │    │ (queries, API keys)   │  │
│  └──────────┘    └──────────────┘    └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┴──────────────────┐
           ▼                                     ▼
┌─────────────────────────┐         ┌─────────────────────────────┐
│     PROCESSAMENT IA     │         │      API REST EXTERNA       │
├─────────────────────────┤         ├─────────────────────────────┤
│ • Parser fitxers        │         │ POST /api/v1/tickets/{key}  │
│ • Inferència estructura │         │ GET  /api/v1/tickets/{key}  │
│ • Generació schema      │         │ PUT  /api/v1/tickets/{key}  │
│ • Classificació tickets │         │                             │
└─────────────────────────┘         └─────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────-─┐
│                    SUPABASE                                      │
├─────────────────────────────────────────────────────────────────-┤
│                                                                  │
│  PostgreSQL                          Storage                     │
│  ───────────                         ───────                     │
│  • users                             • BD xifrades (AES-256)     │
│  • files (metadades)                 • Backup fitxers originals  │
│  • user_files (permisos)                                         │
│  • api_keys                                                      │
│  • saved_queries                                                 │
│                                                                  │
└───────────────────────────────────────────────────────────────-──┘
```

---

## 🔐 Seguretat

| Capa | Protecció |
|------|-----------|
| **Autenticació** | Cookies amb TTL configurable |
| **Dades en repòs** | Xifrat AES-256 a Supabase Storage |
| **API** | Tokens únics (API Keys) per projecte |
| **Integritat** | Hash SHA-256 per verificar fitxers |
| **Transport** | HTTPS |

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
# Editar .env amb les credencials de Supabase

# Executar
python app.py
```

---

## 📁 Estructura del Projecte

```
IBTicket/
├── app.py                 # Entry point Flask
├── requirements.txt       # Dependències
├── docker-compose.yml     
├── Dockerfile
│
├── src/                   # Codi aplicació
│   ├── api/               # REST API (/api/v1)
│   │   ├── routers/       
│   │   ├── controllers/   
│   │   └── middlewares/   
│   │
│   ├── web/               # Portal web
│   │   ├── routers/       
│   │   ├── templates/     # HTML (Jinja2)
│   │   └── static/        # CSS, imatges
│   │
│   ├── services/          # Lògica de negoci
│   └── models/            # Models de dades
│
└── ml/                    # Machine Learning
    ├── training/          
    ├── model_artifacts/   # Models entrenats
    ├── notebooks/         
    └── data/              
```

---

## 🔧 Stack Tecnològic

| Capa | Tecnologia |
|------|------------|
| **Backend** | Python 3.10+ · Flask |
| **Frontend** | HTML · CSS (server-side) |
| **Base de dades** | Supabase (PostgreSQL + Storage) |
| **ML/IA** | Pandas · Scikit-learn |
| **Seguretat** | Cryptography (AES-256) |
| **Desplegament** | Docker · Gunicorn |

---

## 🎨 Branding

**IBTicket** = **I**ce**B**erg**Ticket**

| Element | Significat |
|---------|------------|
| **I** | **AI** (Intel·ligència Artificial) |
| **B** | **Big Data** |
| **Iceberg** | Model Snowflake + profunditat de dades (el que es veu vs el que hi ha sota) |
| **Ticket** | Gestió de tickets |
| 🚢 | Barco amb servidors = IA navegant les dades + "núvol del mar" (cloud) |
| ❄️ | Copos = Snowflake schema |
| 🏔️ | Iceberg = El nom + data warehouse |

---

## 📄 Llicència

Projecte Final de Curs - 2026

---

<div align="center">

**Desenvolupat amb ❄️ per [Joan Linares](https://github.com/JoanLinares)**

</div>
