# Modelo Snowflake para Sistema de Tickets Empresariales

## Descripción General

Este modelo de datos tipo Snowflake está diseñado para gestionar tickets de soporte empresarial de manera escalable y eficiente. El diseño permite análisis multidimensional y reporting avanzado sobre tickets de diferentes tipos, prioridades, colas y lenguajes.

---

## 📊 Diagrama del Modelo Snowflake

### Vista General del Modelo Pro

```
                             ┌─────────────────────┐
                             │   dim_customer      │
                             │─────────────────────│
                    ┌───────→│ customer_key (PK)   │
                    │        │ customer_name       │
                    │        │ email               │
                    │        │ segment_key (FK) ───┼──→ dim_customer_segment
                    │        │ industry_key (FK) ──┼──→ dim_industry
                    │        │ location_key (FK) ──┼──→ dim_location
                    │        └─────────────────────┘
                    │
┌──────────────────┐│        ┌─────────────────────┐       ┌──────────────────┐
│    dim_date      ││        │   dim_agent         │       │    dim_team      │
│──────────────────││        │─────────────────────│       │──────────────────│
│ date_key (PK)    ││   ┌───→│ agent_key (PK)      │──────→│ team_key (PK)    │
│ date             ││   │    │ agent_name          │       │ team_name        │
│ year, month      ││   │    │ email               │       │ manager_name     │
│ quarter, week    ││   │    │ team_key (FK)       │       │ location_key (FK)│
│ is_weekend       ││   │    │ skill_level         │       └──────────────────┘
└────────┬─────────┘│   │    └─────────────────────┘
         │          │   │
         │          │   │    ┌─────────────────────┐       ┌──────────────────┐
         │          │   │    │  dim_ticket_type    │       │   dim_priority   │
         │          │   │    │─────────────────────│       │──────────────────│
         │          │   │    │ type_key (PK)       │       │ priority_key (PK)│
         │          │   │    │ type_name           │       │ priority_name    │
         │          │   │    │ type_description    │       │ priority_level   │
         │          │   │    │ default_sla_hours   │       │ response_time_h  │
         │          │   │    └──────────┬──────────┘       └────────┬─────────┘
         │          │   │               │                           │
         │          │   │               │                           │
         │  ┌───────┴───┴───────────────┴───────────────────────────┴─────────┐
         │  │                       fact_tickets                               │
         │  │──────────────────────────────────────────────────────────────────│
         └─→│ ticket_id (PK)                                                   │
            │ date_key (FK)                    ┌────────────────────────────┐  │
            │ customer_key (FK) ───────────────┘                            │  │
            │ ───────────────────              │                            │  │
            │ submitter_user_id                │                            │  │
            │ submitter_email                  │                            │  │
            │ submitter_name                   │                            │  │
            │ ───────────────────              │                            │  │
            │ agent_key (FK) ──────────────────┐                            │  │
            │ type_key (FK) ───────────────────┼────────────────────────────┘  │
            │ priority_key (FK) ───────────────┼────────────────────────────┐  │
            │ queue_key (FK)                   │                            │  │
            │ language_key (FK)                │                            │  │
            │ status_key (FK)                  │                            │  │
            │ category_key (FK)                │                            │  │
            │ product_key (FK)                 │                            │  │
            │ channel_key (FK)                 │                            │  │
            │ sla_key (FK)                     │                            │  │
            │ ───────────────────              │                            │  │
            │ created_at                       │                            │  │
            │ resolved_at                      │                            │  │
            │ first_response_time_minutes      │                            │  │
            │ resolution_time_minutes          │                            │  │
            │ satisfaction_score               │                            │  │
            │ sla_breached_flag                │                            │  │
            └──────────────┬───────────────────┼────────────────────────────┼──┘
                           │                   │                            │
                  ┌────────┴───────┐  ┌────────┴───────┐       ┌───────────┴─────┐
                  │  dim_queue     │  │  dim_language  │       │   dim_status    │
                  │────────────────│  │────────────────│       │─────────────────│
                  │ queue_key (PK) │  │ language_key   │       │ status_key (PK) │
                  │ queue_name     │  │ language_code  │       │ status_name     │
                  │ queue_category │  │ language_name  │       │ status_category │
                  │ parent_queue ──┼─┐│ native_name    │       │ is_final_state  │
                  └────────────────┘ │└────────────────┘       └─────────────────┘
                          ↑          │
                          └──────────┘
                           (jerarquía)

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────────┐
│  dim_category    │       │   dim_product    │       │ dim_product_category │
│──────────────────│       │──────────────────│       │──────────────────────│
│ category_key (PK)│       │ product_key (PK) │       │ product_category_key │
│ category_name    │       │ product_name     │──────→│ category_name        │
│ parent_category ─┼─┐     │ product_category │       │ parent_category ─────┼─┐
│ category_level   │ │     │ product_version  │       └──────────────────────┘ │
│ category_path    │ │     │ product_status   │                ↑               │
└──────────────────┘ │     └──────────────────┘                └───────────────┘
         ↑           │                                          (jerarquía)
         └───────────┘
         (jerarquía)

┌──────────────────┐       ┌──────────────────────────┐       ┌────────────────┐
│   dim_channel    │       │  bridge_ticket_tags      │       │    dim_tag     │
│──────────────────│       │──────────────────────────│       │────────────────│
│ channel_key (PK) │       │ ticket_id (FK) ──────────┼──────→│ tag_key (PK)   │
│ channel_name     │       │ tag_key (FK)             │       │ tag_name       │
│ channel_type     │       │ tag_order                │←──────│ tag_category   │
│ active_flag      │       └──────────────────────────┘       │ tag_description│
└──────────────────┘                                          └────────────────┘
                                   (relación many-to-many)

┌──────────────────┐       ┌──────────────────────────┐
│     dim_sla      │       │     ticket_text          │
│──────────────────│       │──────────────────────────│
│ sla_key (PK)     │       │ ticket_id (PK, FK) ──────┼──→ fact_tickets
│ sla_name         │       │ subject (TEXT)           │
│ response_time_h  │       │ body (TEXT)              │
│ resolution_time_h│       │ answer (TEXT)            │
│ priority_key (FK)│       │ internal_notes (TEXT)    │
│ segment_key (FK) │       │ resolution_summary (TEXT)│
└──────────────────┘       └──────────────────────────┘
```

### Modelo Simplificado por Áreas Funcionales

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ÁREA DE DIMENSIONES TEMPORALES                    │
├──────────────────────────────────────────────────────────────────────────┤
│  dim_date  │  dim_time  │  (para análisis temporal y patrones horarios) │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        ÁREA DE CLIENTE                                   │
├──────────────────────────────────────────────────────────────────────────┤
│  dim_customer → dim_customer_segment                                     │
│                → dim_industry                                            │
│                → dim_location                                            │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        ÁREA DE AGENTE/EQUIPO                             │
├──────────────────────────────────────────────────────────────────────────┤
│  dim_agent → dim_team → dim_location                                     │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        ÁREA DE CLASIFICACIÓN                             │
├──────────────────────────────────────────────────────────────────────────┤
│  dim_ticket_type  │  dim_priority  │  dim_queue  │  dim_status          │
│  dim_category     │  dim_language  │  dim_channel                        │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        ÁREA DE PRODUCTO                                  │
├──────────────────────────────────────────────────────────────────────────┤
│  dim_product → dim_product_category (jerarquía)                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        TABLA DE HECHOS CENTRAL                           │
├──────────────────────────────────────────────────────────────────────────┤
│                        fact_tickets                                      │
│  • Conecta todas las dimensiones                                        │
│  • Contiene métricas: tiempos, scores, contadores                       │
│  • Registra eventos de tickets                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                        TABLAS DE SOPORTE                                 │
├──────────────────────────────────────────────────────────────────────────┤
│  ticket_text                    (textos largos optimizados)             │
│  bridge_ticket_tags → dim_tag   (relación many-to-many)                 │
│  fact_ticket_status_history     (auditoría de cambios)                  │
│  fact_ticket_interactions       (interacciones detalladas)              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Tabla de Hechos (Fact Table)

### `fact_tickets`

Tabla central que contiene las métricas y referencias a las dimensiones.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticket_id` | BIGINT (PK) | Identificador único del ticket |
| `date_key` | INT (FK) | Referencia a dim_date (fecha de creación) |
| `customer_key` | INT (FK) | Referencia a dim_customer |
| `submitter_user_id` | VARCHAR(100) | ID del usuario que creó el ticket |
| `submitter_email` | VARCHAR(255) | Email de quien reportó el problema |
| `submitter_name` | VARCHAR(255) | Nombre de quien creó el ticket |
| `agent_key` | INT (FK) | Referencia a dim_agent (agente asignado) |
| `type_key` | INT (FK) | Referencia a dim_ticket_type |
| `priority_key` | INT (FK) | Referencia a dim_priority |
| `queue_key` | INT (FK) | Referencia a dim_queue |
| `language_key` | INT (FK) | Referencia a dim_language |
| `status_key` | INT (FK) | Referencia a dim_status |
| `category_key` | INT (FK) | Referencia a dim_category |
| `product_key` | INT (FK) | Referencia a dim_product (opcional) |
| `created_at` | TIMESTAMP | Fecha y hora de creación |
| `resolved_at` | TIMESTAMP | Fecha y hora de resolución |
| `closed_at` | TIMESTAMP | Fecha y hora de cierre |
| `first_response_time_minutes` | DECIMAL(10,2) | Tiempo de primera respuesta en minutos |
| `resolution_time_minutes` | DECIMAL(10,2) | Tiempo de resolución en minutos |
| `response_count` | INT | Número de respuestas |
| `reopened_count` | INT | Número de veces reabierto |
| `escalated_flag` | BOOLEAN | Indica si fue escalado |
| `satisfaction_score` | DECIMAL(3,2) | Puntuación de satisfacción (1-5) |
| `sentiment_score` | DECIMAL(3,2) | Análisis de sentimiento (-1 a 1) |
| `word_count_subject` | INT | Conteo de palabras en asunto |
| `word_count_body` | INT | Conteo de palabras en cuerpo |
| `sla_breached_flag` | BOOLEAN | Indica si se violó el SLA |

---

## Tablas de Dimensiones (Dimension Tables)

### `dim_date`

Dimensión temporal para análisis por periodos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `date_key` | INT (PK) | Clave única (YYYYMMDD) |
| `date` | DATE | Fecha completa |
| `year` | INT | Año |
| `quarter` | INT | Trimestre (1-4) |
| `month` | INT | Mes (1-12) |
| `month_name` | VARCHAR(20) | Nombre del mes |
| `week` | INT | Semana del año |
| `day` | INT | Día del mes |
| `day_of_week` | INT | Día de la semana (1-7) |
| `day_name` | VARCHAR(20) | Nombre del día |
| `is_weekend` | BOOLEAN | Indica si es fin de semana |
| `is_holiday` | BOOLEAN | Indica si es día festivo |
| `fiscal_year` | INT | Año fiscal |
| `fiscal_quarter` | INT | Trimestre fiscal |

### `dim_time`

Dimensión temporal para análisis por horas del día.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `time_key` | INT (PK) | Clave única (HHMMSS) |
| `hour` | INT | Hora (0-23) |
| `minute` | INT | Minuto (0-59) |
| `second` | INT | Segundo (0-59) |
| `time_of_day` | VARCHAR(20) | Periodo (Madrugada, Mañana, Tarde, Noche) |
| `business_hours_flag` | BOOLEAN | Indica si es horario laboral |

### `dim_customer`

Información del cliente que genera el ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `customer_key` | INT (PK) | Clave única |
| `customer_id` | VARCHAR(50) | ID del cliente |
| `customer_name` | VARCHAR(255) | Nombre del cliente |
| `email` | VARCHAR(255) | Correo electrónico |
| `phone` | VARCHAR(50) | Teléfono |
| `company_name` | VARCHAR(255) | Nombre de la empresa |
| `industry_key` | INT (FK) | Referencia a dim_industry |
| `segment_key` | INT (FK) | Referencia a dim_customer_segment |
| `location_key` | INT (FK) | Referencia a dim_location |
| `account_type` | VARCHAR(50) | Tipo de cuenta (Free, Premium, Enterprise) |
| `account_status` | VARCHAR(50) | Estado de la cuenta |
| `registration_date` | DATE | Fecha de registro |
| `lifetime_value` | DECIMAL(12,2) | Valor de vida del cliente |
| `total_tickets` | INT | Total de tickets históricos |
| `vip_flag` | BOOLEAN | Indica si es cliente VIP |

### `dim_customer_segment`

Segmentación de clientes.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `segment_key` | INT (PK) | Clave única |
| `segment_name` | VARCHAR(100) | Nombre del segmento |
| `segment_description` | TEXT | Descripción del segmento |
| `segment_category` | VARCHAR(50) | Categoría (B2B, B2C, Enterprise, SMB) |

### `dim_industry`

Industria o sector del cliente.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `industry_key` | INT (PK) | Clave única |
| `industry_name` | VARCHAR(100) | Nombre de la industria |
| `industry_code` | VARCHAR(20) | Código de industria (NAICS/SIC) |
| `industry_group` | VARCHAR(100) | Grupo de industria |

### `dim_location`

Ubicación geográfica.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `location_key` | INT (PK) | Clave única |
| `country` | VARCHAR(100) | País |
| `country_code` | VARCHAR(3) | Código ISO del país |
| `region` | VARCHAR(100) | Región/Estado/Provincia |
| `city` | VARCHAR(100) | Ciudad |
| `postal_code` | VARCHAR(20) | Código postal |
| `timezone` | VARCHAR(50) | Zona horaria |
| `continent` | VARCHAR(50) | Continente |

### `dim_agent`

Agente o empleado que maneja el ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `agent_key` | INT (PK) | Clave única |
| `agent_id` | VARCHAR(50) | ID del agente |
| `agent_name` | VARCHAR(255) | Nombre del agente |
| `email` | VARCHAR(255) | Correo electrónico |
| `team_key` | INT (FK) | Referencia a dim_team |
| `skill_level` | VARCHAR(50) | Nivel de habilidad (Junior, Mid, Senior) |
| `hire_date` | DATE | Fecha de contratación |
| `active_flag` | BOOLEAN | Indica si está activo |
| `avg_satisfaction_score` | DECIMAL(3,2) | Puntuación promedio de satisfacción |
| `tickets_resolved` | INT | Total de tickets resueltos |

### `dim_team`

Equipos de soporte.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `team_key` | INT (PK) | Clave única |
| `team_name` | VARCHAR(100) | Nombre del equipo |
| `team_description` | TEXT | Descripción del equipo |
| `manager_name` | VARCHAR(255) | Nombre del gerente |
| `specialization` | VARCHAR(100) | Especialización del equipo |
| `location_key` | INT (FK) | Referencia a dim_location |

### `dim_ticket_type`

Tipo de ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `type_key` | INT (PK) | Clave única |
| `type_name` | VARCHAR(100) | Nombre del tipo (Incident, Request, Problem, Task) |
| `type_description` | TEXT | Descripción del tipo |
| `type_code` | VARCHAR(20) | Código del tipo |
| `default_sla_hours` | DECIMAL(5,2) | SLA por defecto en horas |

### `dim_priority`

Nivel de prioridad del ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `priority_key` | INT (PK) | Clave única |
| `priority_name` | VARCHAR(50) | Nombre (Critical, High, Medium, Low, Very Low) |
| `priority_level` | INT | Nivel numérico (1-5) |
| `response_time_hours` | DECIMAL(5,2) | Tiempo de respuesta esperado |
| `resolution_time_hours` | DECIMAL(5,2) | Tiempo de resolución esperado |
| `escalation_threshold_hours` | DECIMAL(5,2) | Umbral para escalación |

### `dim_queue`

Cola o departamento que maneja el ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `queue_key` | INT (PK) | Clave única |
| `queue_name` | VARCHAR(255) | Nombre de la cola |
| `queue_description` | TEXT | Descripción |
| `queue_category` | VARCHAR(100) | Categoría principal |
| `parent_queue_key` | INT (FK) | Referencia a cola padre (jerarquía) |
| `active_flag` | BOOLEAN | Indica si está activa |
| `business_hours_only` | BOOLEAN | Solo horario laboral |

**Ejemplos de colas basados en los datos:**
- Technical Support
- Billing and Payments
- Returns and Exchanges
- Sales and Pre-Sales
- Service Outages and Maintenance
- Product Support
- IT Support
- Customer Service

### `dim_status`

Estado del ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `status_key` | INT (PK) | Clave única |
| `status_name` | VARCHAR(50) | Nombre del estado |
| `status_category` | VARCHAR(50) | Categoría (Open, In Progress, Resolved, Closed, Cancelled) |
| `is_final_state` | BOOLEAN | Indica si es estado final |
| `allows_reopening` | BOOLEAN | Permite reapertura |
| `display_order` | INT | Orden de visualización |

### `dim_category`

Categoría del ticket basada en el problema o solicitud.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `category_key` | INT (PK) | Clave única |
| `category_name` | VARCHAR(100) | Nombre de la categoría |
| `parent_category_key` | INT (FK) | Referencia a categoría padre |
| `category_level` | INT | Nivel en jerarquía (1, 2, 3) |
| `category_path` | VARCHAR(500) | Ruta completa de jerarquía |
| `active_flag` | BOOLEAN | Indica si está activa |

**Ejemplos de categorías basados en los datos:**
- Security (Data Breach, Outage, Disruption)
- Account (Disruption, Access Issues)
- Product (Feature, Configuration)
- Network (Connectivity, VPN, Hardware)
- Bug (Crash, Performance)
- Billing (Payment, Invoice)
- Documentation (Inquiry, Feedback)

### `dim_language`

Idioma del ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `language_key` | INT (PK) | Clave única |
| `language_code` | VARCHAR(10) | Código ISO (en, de, es, fr) |
| `language_name` | VARCHAR(100) | Nombre del idioma |
| `native_name` | VARCHAR(100) | Nombre nativo |
| `is_rtl` | BOOLEAN | Indica si es derecha a izquierda |
| `active_flag` | BOOLEAN | Indica si está activo |

### `dim_product`

Producto o servicio relacionado con el ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_key` | INT (PK) | Clave única |
| `product_id` | VARCHAR(50) | ID del producto |
| `product_name` | VARCHAR(255) | Nombre del producto |
| `product_category_key` | INT (FK) | Referencia a dim_product_category |
| `product_version` | VARCHAR(50) | Versión del producto |
| `product_status` | VARCHAR(50) | Estado (Active, Deprecated, Beta) |
| `release_date` | DATE | Fecha de lanzamiento |
| `end_of_life_date` | DATE | Fecha de fin de vida |

### `dim_product_category`

Categoría de productos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_category_key` | INT (PK) | Clave única |
| `category_name` | VARCHAR(100) | Nombre de la categoría |
| `parent_category_key` | INT (FK) | Referencia a categoría padre |
| `category_description` | TEXT | Descripción |

### `dim_channel`

Canal por el que se creó el ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `channel_key` | INT (PK) | Clave única |
| `channel_name` | VARCHAR(50) | Nombre (Email, Web Portal, Phone, Chat, API, Mobile App) |
| `channel_type` | VARCHAR(50) | Tipo (Digital, Voice, Self-Service) |
| `active_flag` | BOOLEAN | Indica si está activo |

### `dim_sla`

Acuerdos de nivel de servicio.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sla_key` | INT (PK) | Clave única |
| `sla_name` | VARCHAR(100) | Nombre del SLA |
| `sla_description` | TEXT | Descripción |
| `response_time_hours` | DECIMAL(5,2) | Tiempo de respuesta en horas |
| `resolution_time_hours` | DECIMAL(5,2) | Tiempo de resolución en horas |
| `business_hours_only` | BOOLEAN | Solo horario laboral |
| `priority_key` | INT (FK) | Referencia a dim_priority |
| `customer_segment_key` | INT (FK) | Referencia a dim_customer_segment |

---

## Tabla Bridge para Tags

### `bridge_ticket_tags`

Permite múltiples tags por ticket (relación many-to-many).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticket_id` | BIGINT (FK) | Referencia a fact_tickets |
| `tag_key` | INT (FK) | Referencia a dim_tag |
| `tag_order` | INT | Orden del tag |

### `dim_tag`

Etiquetas o tags del ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tag_key` | INT (PK) | Clave única |
| `tag_name` | VARCHAR(100) | Nombre del tag |
| `tag_category` | VARCHAR(50) | Categoría del tag |
| `tag_description` | TEXT | Descripción |
| `active_flag` | BOOLEAN | Indica si está activo |

**Ejemplos de tags basados en los datos:**
- Security, Outage, Disruption, Data Breach
- Account, Network, Hardware, Software
- Bug, Feature, Performance, Compatibility
- IT, Tech Support, Documentation, Feedback
- VPN, Billing, Payment, Marketing

---

## Tablas de Texto (Text Tables)

Para optimizar el almacenamiento, los campos de texto largo se separan:

### `ticket_text`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticket_id` | BIGINT (PK, FK) | Referencia a fact_tickets |
| `subject` | TEXT | Asunto del ticket |
| `body` | TEXT | Cuerpo/descripción del ticket |
| `answer` | TEXT | Respuesta o solución |
| `internal_notes` | TEXT | Notas internas |
| `resolution_summary` | TEXT | Resumen de resolución |

---

## Tabla de Historial de Estado

### `fact_ticket_status_history`

Seguimiento de cambios de estado.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `history_id` | BIGINT (PK) | Clave única |
| `ticket_id` | BIGINT (FK) | Referencia a fact_tickets |
| `status_key` | INT (FK) | Referencia a dim_status |
| `agent_key` | INT (FK) | Agente que realizó el cambio |
| `changed_at` | TIMESTAMP | Fecha y hora del cambio |
| `duration_minutes` | DECIMAL(10,2) | Tiempo en este estado |
| `previous_status_key` | INT (FK) | Estado anterior |
| `change_reason` | TEXT | Razón del cambio |

---

## Tabla de Interacciones

### `fact_ticket_interactions`

Registro de todas las interacciones del ticket.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `interaction_id` | BIGINT (PK) | Clave única |
| `ticket_id` | BIGINT (FK) | Referencia a fact_tickets |
| `interaction_date_key` | INT (FK) | Referencia a dim_date |
| `interaction_time_key` | INT (FK) | Referencia a dim_time |
| `agent_key` | INT (FK) | Referencia a dim_agent |
| `interaction_type` | VARCHAR(50) | Tipo (Reply, Note, Status Change, Escalation) |
| `channel_key` | INT (FK) | Referencia a dim_channel |
| `interaction_text` | TEXT | Contenido de la interacción |
| `interaction_timestamp` | TIMESTAMP | Fecha y hora |
| `duration_seconds` | INT | Duración de la interacción |
| `is_customer_facing` | BOOLEAN | Visible para el cliente |

---

## Métricas Calculadas y KPIs

### Consultas SQL de Ejemplo

#### 1. Tiempo Promedio de Resolución por Prioridad

```sql
SELECT 
    p.priority_name,
    AVG(f.resolution_time_minutes) / 60 as avg_resolution_hours,
    COUNT(*) as ticket_count
FROM fact_tickets f
JOIN dim_priority p ON f.priority_key = p.priority_key
WHERE f.resolved_at IS NOT NULL
GROUP BY p.priority_name
ORDER BY p.priority_level;
```

#### 2. Tickets por Cola y Estado

```sql
SELECT 
    q.queue_name,
    s.status_name,
    COUNT(*) as ticket_count,
    AVG(f.resolution_time_minutes) as avg_resolution_minutes
FROM fact_tickets f
JOIN dim_queue q ON f.queue_key = q.queue_key
JOIN dim_status s ON f.status_key = s.status_key
GROUP BY q.queue_name, s.status_name
ORDER BY ticket_count DESC;
```

#### 3. Performance de Agentes

```sql
SELECT 
    a.agent_name,
    t.team_name,
    COUNT(*) as tickets_handled,
    AVG(f.satisfaction_score) as avg_satisfaction,
    AVG(f.first_response_time_minutes) as avg_first_response,
    SUM(CASE WHEN f.sla_breached_flag = TRUE THEN 1 ELSE 0 END) as sla_breaches
FROM fact_tickets f
JOIN dim_agent a ON f.agent_key = a.agent_key
JOIN dim_team t ON a.team_key = t.team_key
WHERE f.resolved_at >= DATEADD(month, -1, GETDATE())
GROUP BY a.agent_name, t.team_name
ORDER BY tickets_handled DESC;
```

#### 4. Análisis de Tendencias por Idioma

```sql
SELECT 
    d.year,
    d.month_name,
    l.language_name,
    COUNT(*) as ticket_count,
    AVG(f.sentiment_score) as avg_sentiment
FROM fact_tickets f
JOIN dim_date d ON f.date_key = d.date_key
JOIN dim_language l ON f.language_key = l.language_key
GROUP BY d.year, d.month, d.month_name, l.language_name
ORDER BY d.year DESC, d.month DESC;
```

#### 5. Categorías más Comunes por Producto

```sql
SELECT 
    p.product_name,
    c.category_name,
    COUNT(*) as ticket_count,
    AVG(f.resolution_time_minutes) / 60 as avg_resolution_hours
FROM fact_tickets f
JOIN dim_product p ON f.product_key = p.product_key
JOIN dim_category c ON f.category_key = c.category_key
WHERE f.created_at >= DATEADD(month, -3, GETDATE())
GROUP BY p.product_name, c.category_name
HAVING COUNT(*) > 5
ORDER BY ticket_count DESC;
```

#### 6. Análisis de Tags

```sql
SELECT 
    t.tag_name,
    COUNT(DISTINCT bt.ticket_id) as ticket_count,
    AVG(f.resolution_time_minutes) / 60 as avg_resolution_hours,
    AVG(f.satisfaction_score) as avg_satisfaction
FROM bridge_ticket_tags bt
JOIN dim_tag t ON bt.tag_key = t.tag_key
JOIN fact_tickets f ON bt.ticket_id = f.ticket_id
WHERE f.created_at >= DATEADD(month, -1, GETDATE())
GROUP BY t.tag_name
HAVING COUNT(DISTINCT bt.ticket_id) > 10
ORDER BY ticket_count DESC;
```

---

## Ventajas del Modelo Snowflake

1. **Normalización**: Reduce la redundancia de datos y mejora la integridad
2. **Flexibilidad**: Permite agregar nuevas dimensiones fácilmente
3. **Escalabilidad**: Maneja grandes volúmenes de tickets eficientemente
4. **Consultas Optimizadas**: Facilita análisis complejos y reporting
5. **Mantenimiento**: Simplifica actualizaciones de datos de referencia
6. **Multiidioma**: Soporta tickets en múltiples idiomas
7. **Jerarquías**: Permite análisis drill-down/roll-up en categorías, ubicaciones, etc.
8. **Auditoría**: Mantiene historial completo de cambios
9. **BI-Friendly**: Compatible con herramientas de Business Intelligence

---

## Implementación y ETL

### 🔄 Flujo del Proceso ETL

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PROCESO ETL COMPLETO                           │
└─────────────────────────────────────────────────────────────────────────┘

   ╔═══════════════════════════════════════════════════════════════╗
   ║                    FASE 1: EXTRACT (Extracción)               ║
   ╚═══════════════════════════════════════════════════════════════╝
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼─────┐          ┌──────▼──────┐         ┌──────▼──────┐
   │  Sistema │          │   Base de   │         │  APIs       │
   │    CRM   │          │    Datos    │         │  Externas   │
   │  Tickets │          │Transaccional│         │ (Zendesk,   │
   └────┬─────┘          └──────┬──────┘         │  Jira...)   │
        │                       │                 └──────┬──────┘
        │                       │                        │
        └───────────────────────┼────────────────────────┘
                                │
                         ┌──────▼──────┐
                         │  Archivos   │
                         │  CSV, JSON  │
                         │   Parquet   │
                         └──────┬──────┘
                                │
   ╔═══════════════════════════▼═══════════════════════════════════╗
   ║                FASE 2: TRANSFORM (Transformación)             ║
   ╚═══════════════════════════════════════════════════════════════╝
                                │
                    ┌───────────┴───────────┐
                    │  1. Limpieza de Datos │
                    │  • Valores nulos      │
                    │  • Duplicados         │
                    │  • Formatos           │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 2. Normalización      │
                    │  • Encoding (UTF-8)   │
                    │  • Espacios blancos   │
                    │  • Mayús/Minús        │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 3. Detección Idioma   │
                    │  • ML/Reglas          │
                    │  • Asignar lang_key   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 4. Análisis NLP       │
                    │  • Sentimiento        │
                    │  • Palabras clave     │
                    │  • Categorización     │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 5. Asignación Claves  │
                    │  • Surrogate keys     │
                    │  • Foreign keys       │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 6. Cálculo Métricas   │
                    │  • Tiempos respuesta  │
                    │  • Tiempos resolución │
                    │  • Conteo palabras    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 7. Enriquecimiento    │
                    │  • Geolocalización    │
                    │  • Tags automáticos   │
                    │  • Categorías         │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ 8. Validación Calidad │
                    │  • Business rules     │
                    │  • Rangos válidos     │
                    │  • Integridad         │
                    └───────────┬───────────┘
                                │
   ╔═══════════════════════════▼═══════════════════════════════════╗
   ║                    FASE 3: LOAD (Carga)                       ║
   ╚═══════════════════════════════════════════════════════════════╝
                                │
                    ┌───────────┴───────────┐
                    │   ¿Tipo de Tabla?     │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────▼────────┐    ┌────────▼─────────┐    ┌───────▼────────┐
   │ Dimensiones │    │ Tabla de Hechos  │    │ Tablas Bridge  │
   │  (SCD T-2)  │    │  fact_tickets    │    │bridge_tickets  │
   │             │    │                  │    │     _tags      │
   │ • date      │    │ Métricas y FKs   │    │                │
   │ • customer  │    │                  │    │ Many-to-Many   │
   │ • agent     │    └──────────────────┘    └────────────────┘
   │ • priority  │             │
   │ • queue     │             │
   │ • etc...    │             │
   └─────────────┘             │
        │                      │
        └──────────────────────┼──────────────────────┐
                               │                      │
                     ┌─────────▼────────┐   ┌────────▼────────┐
                     │  Tablas Texto    │   │   Historial     │
                     │  ticket_text     │   │ status_history  │
                     │                  │   │  interactions   │
                     │ Textos largos    │   │                 │
                     └──────────────────┘   └─────────────────┘
                               │
   ╔═══════════════════════════▼═══════════════════════════════════╗
   ║                 FASE 4: VALIDACIÓN                            ║
   ╚═══════════════════════════════════════════════════════════════╝
                               │
                    ┌──────────▼───────────┐
                    │  Verificar           │
                    │  Integridad          │
                    │  Referencial         │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Validar Métricas    │
                    │  (rangos esperados)  │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Contar Registros    │
                    │  (reconciliación)    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │    ¿Todo OK?         │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    │                      │
             ┌──────▼──────┐        ┌─────▼──────┐
             │   ✓ ÉXITO   │        │  ✗ ERROR   │
             │             │        │            │
             │ • Commit    │        │ • Rollback │
             │ • Log OK    │        │ • Log error│
             │ • Metadatos │        │ • Alertas  │
             └─────────────┘        └────────────┘
```

### 📈 Flujo de Ciclo de Vida de un Ticket

```
┌─────────────────────────────────────────────────────────────────────────┐
│               CICLO DE VIDA DE UN TICKET EN EL SISTEMA                  │
└─────────────────────────────────────────────────────────────────────────┘

      ┌──────────────────┐
      │  Ticket Creado   │
      │  (Email/Portal)  │
      └────────┬─────────┘
               │
               ▼
      ┌────────────────────────────┐
      │  Recepción y Parsing       │
      │  • Extraer subject/body    │
      │  • Identificar remitente   │
      │  • Capturar user_id        │
      │  • Capturar email          │
      │  • Capturar nombre         │
      │  • Timestamp               │
      └────────┬───────────────────┘
               │
               ▼
      ┌────────────────────────────┐
      │  Enriquecimiento IA        │
      │  • Detectar idioma         │──→ INSERT dim_language (si nuevo)
      │  • Análisis sentimiento    │
      │  • Identificar categoría   │──→ BUSCAR dim_category
      │  • Sugerir prioridad       │──→ BUSCAR dim_priority
      │  • Auto-tags               │──→ INSERT bridge_ticket_tags
      └────────┬───────────────────┘
               │
               ▼
      ┌────────────────────────────┐
      │  Enrutamiento              │
      │  Basado en:                │
      │  • Prioridad               │
      │  • Categoría               │──→ ASIGNAR dim_queue
      │  • Disponibilidad agentes  │──→ ASIGNAR dim_agent
      │  • SLA                     │──→ VINCULAR dim_sla
      └────────┬───────────────────┘
               │
               ▼
      ┌────────────────────────────┐
      │  INSERT fact_tickets       │
      │  • ticket_id (nuevo)       │
      │  • submitter_user_id       │
      │  • submitter_email         │
      │  • submitter_name          │
      │  • customer_key (lookup)   │
      │  • Todas las FK            │
      │  • created_at = NOW()      │
      │  • status_key = "New"      │
      └────────┬───────────────────┘
               │
               ▼
      ┌────────────────────────────┐
      │  INSERT ticket_text        │
      │  • subject                 │
      │  • body                    │
      └────────┬───────────────────┘
               │
               ▼
      ┌────────────────────────────┐
      │  INSERT status_history     │
      │  • Estado: New             │
      │  • changed_at = NOW()      │
      └────────┬───────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
   ┌─────────┐   ┌─────────────┐
   │ Agente  │   │  Análisis   │
   │ Trabaja │   │   Tiempo    │──→ Data Warehouse
   │  Ticket │   │    Real     │──→ Dashboards
   └────┬────┘   └─────────────┘
        │
        ▼
   ┌──────────────────────────┐
   │  Interacciones           │
   │  • Reply                 │──→ INSERT fact_ticket_interactions
   │  • Note                  │
   │  • Status Change         │──→ UPDATE fact_tickets (status_key)
   │  • Escalation            │──→ INSERT status_history
   └────────┬─────────────────┘
            │
            ▼
   ┌──────────────────────────┐
   │  ¿Resuelto?              │
   └────┬──────────────┬──────┘
        │ No           │ Sí
        │              ▼
        │     ┌──────────────────────────┐
        │     │  UPDATE fact_tickets     │
        │     │  • resolved_at = NOW()   │
        │     │  • resolution_time       │
        │     │  • status = "Resolved"   │
        │     └────────┬─────────────────┘
        │              │
        └──────────────┤
                       ▼
              ┌──────────────────────────┐
              │  ¿Cliente Satisfecho?    │
              └────┬──────────────┬──────┘
                   │              │
                   ▼              ▼
            ┌──────────┐   ┌──────────────┐
            │  Cerrar  │   │  Reabrir     │
            │  Ticket  │   │  Ticket      │
            └────┬─────┘   └───┬──────────┘
                 │             │
                 │             │ reopened_count++
                 │             └──────┐
                 ▼                    │
        ┌────────────────┐            │
        │ UPDATE         │            │
        │ • closed_at    │            │
        │ • status=Close │            │
        └────────┬───────┘            │
                 │                    │
                 └────────────────────┘
                          │
                          ▼
                 ┌────────────────────┐
                 │  Análisis Post     │
                 │  • KPIs            │
                 │  • Satisfacción    │
                 │  • Tendencias      │
                 │  • ML Training     │
                 └────────────────────┘
```

### 🔄 Slowly Changing Dimension (SCD Type 2)

Proceso para mantener historial de cambios en dimensiones:

```
┌─────────────────────────────────────────────────────────────────┐
│           PROCESO SCD TYPE 2 - dim_customer (ejemplo)           │
└─────────────────────────────────────────────────────────────────┘

      Nuevo registro o actualización
                 │
                 ▼
      ┌──────────────────────┐
      │  ¿Existe customer_id │
      │  en dimensión?       │
      └──────┬──────────┬────┘
             │ NO       │ SÍ
             │          │
             ▼          ▼
      ┌──────────┐  ┌────────────────────┐
      │  INSERT  │  │  ¿Datos cambiaron? │
      │  Nuevo   │  └──────┬──────┬──────┘
      │  Registro│         │ NO   │ SÍ
      │          │         │      │
      │ customer │         ▼      ▼
      │ _key = 1 │  ┌──────────┐  ┌─────────────────┐
      │ is_curre │  │   SKIP   │  │ UPDATE registro │
      │ nt = T   │  │  (no     │  │    anterior:    │
      │ valid_fr │  │  hacer   │  │ is_current = F  │
      │ om = NOW │  │  nada)   │  │ valid_to = NOW  │
      │ valid_to │  └──────────┘  └────────┬────────┘
      │ = NULL   │                         │
      └──────────┘                         ▼
             │                  ┌──────────────────────┐
             │                  │  INSERT nuevo reg:   │
             │                  │  customer_key = 2    │
             │                  │  is_current = TRUE   │
             │                  │  valid_from = NOW    │
             │                  │  valid_to = NULL     │
             │                  │  version++           │
             │                  └──────────┬───────────┘
             │                             │
             └─────────────────────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │  COMPLETADO   │
                        │               │
                        │  Historial    │
                        │  preservado   │
                        └───────────────┘

Ejemplo concreto:

ANTES:
┌──────────┬─────────┬───────────┬────────────┬──────────┬──────────┐
│customer  │customer │  email    │is_current  │valid_from│valid_to  │
│_key      │_id      │           │            │          │          │
├──────────┼─────────┼───────────┼────────────┼──────────┼──────────┤
│   123    │  C001   │old@e.com  │   TRUE     │2025-01-01│   NULL   │
└──────────┴─────────┴───────────┴────────────┴──────────┴──────────┘

Cliente cambia email → TRIGGER SCD Type 2

DESPUÉS:
┌──────────┬─────────┬───────────┬────────────┬──────────┬──────────┐
│customer  │customer │  email    │is_current  │valid_from│valid_to  │
│_key      │_id      │           │            │          │          │
├──────────┼─────────┼───────────┼────────────┼──────────┼──────────┤
│   123    │  C001   │old@e.com  │   FALSE    │2025-01-01│2026-01-19│ ← actualizado
│   456    │  C001   │new@e.com  │   TRUE     │2026-01-19│   NULL   │ ← nuevo
└──────────┴─────────┴───────────┴────────────┴──────────┴──────────┘

✓ Historial preservado
✓ Consultas pueden ver estado en cualquier momento
✓ fact_tickets mantiene integridad referencial
```

### Proceso ETL Recomendado

1. **Extract**: Extracción de datos de sistemas fuente (CRM, sistema de tickets)
2. **Transform**: 
   - Limpieza de datos
   - Normalización de texto
   - Asignación de claves surrogate
   - Cálculo de métricas
   - Detección de idioma
   - Análisis de sentimiento
3. **Load**: 
   - Carga de dimensiones (SCD Type 2 para historial)
   - Carga de tabla de hechos
   - Actualización de tablas bridge

### Consideraciones de Performance

- Índices en claves primarias y foráneas
- Particionamiento por fecha en fact_tickets
- Vistas materializadas para consultas frecuentes
- Compresión de columnas de texto
- Índices de texto completo (Full-Text Search) en campos de texto
- Índices en submitter_email y submitter_user_id para búsquedas rápidas

---

## 👤 Captura de Información del Creador del Ticket

### Campos en fact_tickets

El modelo incluye campos denormalizados para capturar rápidamente la información de quien crea/reporta el ticket:

- **`submitter_user_id`**: ID del usuario en el sistema (puede venir de Active Directory, LDAP, sistema interno)
- **`submitter_email`**: Email de quien reportó el problema
- **`submitter_name`**: Nombre completo del creador del ticket
- **`customer_key`**: Referencia a dim_customer (se hace lookup/upsert durante ETL)

### Ejemplo SQL: Crear Ticket con Información del Submitter

```sql
-- 1. Buscar o crear customer en dim_customer
INSERT INTO dim_customer (
    customer_id, 
    customer_name, 
    email,
    registration_date,
    account_status
)
VALUES (
    'USR12345',
    'Juan Pérez',
    'juan.perez@empresa.com',
    CURRENT_DATE,
    'Active'
)
ON CONFLICT (email) DO UPDATE 
SET 
    customer_name = EXCLUDED.customer_name,
    customer_id = EXCLUDED.customer_id
RETURNING customer_key;

-- 2. Insertar ticket con toda la información del submitter
INSERT INTO fact_tickets (
    ticket_id,
    date_key,
    customer_key,
    submitter_user_id,
    submitter_email,
    submitter_name,
    agent_key,
    type_key,
    priority_key,
    queue_key,
    language_key,
    status_key,
    category_key,
    created_at,
    sla_breached_flag
)
VALUES (
    NEXTVAL('ticket_id_seq'),
    20260119,                          -- date_key en formato YYYYMMDD
    (SELECT customer_key FROM dim_customer WHERE email = 'juan.perez@empresa.com'),
    'USR12345',                        -- submitter_user_id
    'juan.perez@empresa.com',          -- submitter_email
    'Juan Pérez',                      -- submitter_name
    (SELECT agent_key FROM dim_agent WHERE agent_name = 'Auto-assigned' LIMIT 1),
    (SELECT type_key FROM dim_ticket_type WHERE type_name = 'Incident'),
    (SELECT priority_key FROM dim_priority WHERE priority_name = 'High'),
    (SELECT queue_key FROM dim_queue WHERE queue_name = 'Technical Support'),
    (SELECT language_key FROM dim_language WHERE language_code = 'es'),
    (SELECT status_key FROM dim_status WHERE status_name = 'New'),
    (SELECT category_key FROM dim_category WHERE category_name = 'Network'),
    CURRENT_TIMESTAMP,
    FALSE
);
```

### Pseudocódigo ETL para Capturar Submitter Info

```python
def process_incoming_ticket(ticket_data):
    """
    Procesa un ticket entrante y captura información del creador
    """
    # 1. Extraer información del remitente
    submitter_info = extract_submitter_info(ticket_data)
    # submitter_info = {
    #     'user_id': 'USR12345',
    #     'email': 'juan.perez@empresa.com',
    #     'name': 'Juan Pérez',
    #     'department': 'IT',
    #     'location': 'Madrid'
    # }
    
    # 2. Buscar o crear en dim_customer
    customer_key = upsert_customer(submitter_info)
    
    # 3. Procesar el contenido del ticket
    ticket_content = {
        'subject': ticket_data['subject'],
        'body': ticket_data['body'],
        'detected_language': detect_language(ticket_data['body']),
        'sentiment': analyze_sentiment(ticket_data['body']),
        'suggested_category': classify_category(ticket_data['subject']),
        'suggested_priority': suggest_priority(ticket_data)
    }
    
    # 4. Obtener claves de dimensiones
    dimension_keys = {
        'date_key': generate_date_key(datetime.now()),
        'customer_key': customer_key,
        'language_key': lookup_language(ticket_content['detected_language']),
        'type_key': lookup_ticket_type('Incident'),
        'priority_key': lookup_priority(ticket_content['suggested_priority']),
        'queue_key': route_to_queue(ticket_content['suggested_category']),
        'status_key': lookup_status('New'),
        'category_key': lookup_category(ticket_content['suggested_category']),
        'channel_key': lookup_channel(ticket_data['source'])  # email, portal, api, etc.
    }
    
    # 5. Insertar en fact_tickets CON información del submitter
    ticket_id = insert_ticket(
        dimension_keys=dimension_keys,
        submitter_user_id=submitter_info['user_id'],
        submitter_email=submitter_info['email'],
        submitter_name=submitter_info['name'],
        created_at=datetime.now()
    )
    
    # 6. Insertar texto del ticket
    insert_ticket_text(
        ticket_id=ticket_id,
        subject=ticket_content['subject'],
        body=ticket_content['body']
    )
    
    # 7. Registrar en historial de estado
    insert_status_history(
        ticket_id=ticket_id,
        status_key=dimension_keys['status_key'],
        changed_at=datetime.now(),
        agent_key=None,  # Creación automática
        change_reason='Ticket creado por usuario'
    )
    
    # 8. Insertar tags automáticos
    auto_tags = extract_tags(ticket_content['subject'], ticket_content['body'])
    for tag_name in auto_tags:
        tag_key = lookup_or_create_tag(tag_name)
        insert_ticket_tag(ticket_id, tag_key)
    
    return ticket_id


def extract_submitter_info(ticket_data):
    """
    Extrae información del creador desde diferentes fuentes
    """
    # Desde email header
    if ticket_data['source'] == 'email':
        return {
            'user_id': extract_user_id_from_email(ticket_data['from_email']),
            'email': ticket_data['from_email'],
            'name': ticket_data['from_name'],
            'department': lookup_department_by_email(ticket_data['from_email']),
            'location': lookup_location_by_email(ticket_data['from_email'])
        }
    
    # Desde portal web (usuario autenticado)
    elif ticket_data['source'] == 'web_portal':
        user = get_authenticated_user(ticket_data['session_token'])
        return {
            'user_id': user['id'],
            'email': user['email'],
            'name': f"{user['first_name']} {user['last_name']}",
            'department': user['department'],
            'location': user['location']
        }
    
    # Desde API externa
    elif ticket_data['source'] == 'api':
        return {
            'user_id': ticket_data['api_user_id'],
            'email': ticket_data['api_user_email'],
            'name': ticket_data['api_user_name'],
            'department': ticket_data.get('department', 'Unknown'),
            'location': ticket_data.get('location', 'Unknown')
        }
    
    # Default
    return {
        'user_id': 'UNKNOWN',
        'email': 'unknown@system.com',
        'name': 'Unknown User',
        'department': 'Unknown',
        'location': 'Unknown'
    }


def upsert_customer(submitter_info):
    """
    Inserta o actualiza customer en dim_customer
    """
    # Buscar por email
    customer = db.query("""
        SELECT customer_key 
        FROM dim_customer 
        WHERE email = %s
    """, (submitter_info['email'],))
    
    if customer:
        # Actualizar información si cambió
        db.execute("""
            UPDATE dim_customer
            SET 
                customer_name = %s,
                customer_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE customer_key = %s
        """, (
            submitter_info['name'],
            submitter_info['user_id'],
            customer['customer_key']
        ))
        return customer['customer_key']
    else:
        # Insertar nuevo customer
        customer_key = db.execute("""
            INSERT INTO dim_customer (
                customer_id,
                customer_name,
                email,
                phone,
                segment_key,
                industry_key,
                location_key,
                account_type,
                account_status,
                registration_date,
                total_tickets,
                vip_flag
            ) VALUES (
                %s, %s, %s, NULL,
                (SELECT segment_key FROM dim_customer_segment WHERE segment_name = 'Standard'),
                (SELECT industry_key FROM dim_industry WHERE industry_name = 'Technology'),
                (SELECT location_key FROM dim_location WHERE city = %s),
                'Standard',
                'Active',
                CURRENT_DATE,
                0,
                FALSE
            ) RETURNING customer_key
        """, (
            submitter_info['user_id'],
            submitter_info['name'],
            submitter_info['email'],
            submitter_info['location']
        ))
        return customer_key
```

### Consultas de Análisis por Creador del Ticket

```sql
-- Tickets por usuario (top reportadores)
SELECT 
    submitter_email,
    submitter_name,
    COUNT(*) as total_tickets,
    AVG(resolution_time_minutes)/60 as avg_resolution_hours,
    SUM(CASE WHEN sla_breached_flag = TRUE THEN 1 ELSE 0 END) as sla_breaches
FROM fact_tickets
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY submitter_email, submitter_name
ORDER BY total_tickets DESC
LIMIT 20;

-- Tickets por departamento del creador
SELECT 
    c.company_name,
    l.city as location,
    cs.segment_name,
    COUNT(*) as tickets,
    AVG(f.satisfaction_score) as avg_satisfaction
FROM fact_tickets f
JOIN dim_customer c ON f.customer_key = c.customer_key
JOIN dim_location l ON c.location_key = l.location_key
JOIN dim_customer_segment cs ON c.segment_key = cs.segment_key
WHERE f.created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY c.company_name, l.city, cs.segment_name
ORDER BY tickets DESC;

-- Historial completo de un usuario
SELECT 
    f.ticket_id,
    f.submitter_email,
    f.submitter_name,
    f.created_at,
    f.resolved_at,
    s.status_name,
    p.priority_name,
    c.category_name,
    tt.subject,
    f.satisfaction_score
FROM fact_tickets f
JOIN dim_status s ON f.status_key = s.status_key
JOIN dim_priority p ON f.priority_key = p.priority_key
JOIN dim_category c ON f.category_key = c.category_key
LEFT JOIN ticket_text tt ON f.ticket_id = tt.ticket_id
WHERE f.submitter_email = 'juan.perez@empresa.com'
ORDER BY f.created_at DESC;

-- Usuarios más problemáticos (muchos tickets sin resolver)
SELECT 
    submitter_email,
    submitter_name,
    COUNT(*) as open_tickets,
    MIN(created_at) as oldest_ticket,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/3600) as avg_hours_open
FROM fact_tickets f
JOIN dim_status s ON f.status_key = s.status_key
WHERE s.status_category IN ('Open', 'In Progress')
GROUP BY submitter_email, submitter_name
HAVING COUNT(*) > 3
ORDER BY open_tickets DESC, avg_hours_open DESC;
```

### Validación en ETL

```python
def validate_submitter_info(ticket_id, submitter_info):
    """
    Valida que la información del submitter se guardó correctamente
    """
    ticket = db.query("""
        SELECT 
            submitter_user_id,
            submitter_email,
            submitter_name,
            customer_key
        FROM fact_tickets
        WHERE ticket_id = %s
    """, (ticket_id,))
    
    if not ticket:
        log.error(f"Ticket {ticket_id} no encontrado después de inserción")
        return False
    
    # Validar que los campos no estén vacíos
    if not ticket['submitter_email']:
        log.error(f"Ticket {ticket_id}: submitter_email está vacío")
        return False
    
    if not ticket['submitter_user_id']:
        log.warning(f"Ticket {ticket_id}: submitter_user_id está vacío")
    
    if not ticket['customer_key']:
        log.error(f"Ticket {ticket_id}: customer_key no asignado")
        return False
    
    # Validar que el customer existe
    customer = db.query("""
        SELECT customer_key, email
        FROM dim_customer
        WHERE customer_key = %s
    """, (ticket['customer_key'],))
    
    if not customer:
        log.error(f"Ticket {ticket_id}: customer_key {ticket['customer_key']} no existe en dim_customer")
        return False
    
    # Verificar que el email coincide
    if customer['email'] != ticket['submitter_email']:
        log.warning(f"Ticket {ticket_id}: email mismatch - ticket: {ticket['submitter_email']}, customer: {customer['email']}")
    
    log.info(f"Ticket {ticket_id}: información del submitter validada correctamente")
    return True
```

---

## Extensiones Futuras

- **Análisis de Sentimiento Avanzado**: Integración con ML para análisis emocional
- **Predicción de Escalación**: Modelo predictivo para identificar tickets en riesgo
- **Clustering de Tickets**: Agrupación automática de tickets similares
- **Chatbot Integration**: Dimensión para interacciones con bots
- **Knowledge Base**: Relación con artículos de base de conocimiento
- **Feedback Loop**: Tabla para retroalimentación post-resolución
- **Costos**: Dimensión de costos por ticket/resolución
- **Social Media**: Integración con tickets desde redes sociales

---

## Notas de Implementación

Este modelo ha sido diseñado considerando:
- Tickets multiidioma (español, inglés, alemán, etc.)
- Múltiples tipos de tickets (Incident, Request, Problem)
- Diferentes prioridades (Critical, High, Medium, Low, Very Low)
- Diversas colas/departamentos
- Sistema de etiquetado flexible
- Trazabilidad completa del ciclo de vida del ticket
- Métricas de rendimiento y satisfacción
- Cumplimiento de SLA

El modelo es adaptable y puede personalizarse según las necesidades específicas de cada organización.
