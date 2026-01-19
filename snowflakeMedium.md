# Modelo Snowflake MEDIUM - Sistema de Tickets

## 🎯 Propósito

Modelo **intermedio** diseñado para **empresas en crecimiento** que necesitan más capacidad de análisis sin la complejidad del modelo Expert. Balance perfecto entre funcionalidad y simplicidad.

**Ideal para:**
- Empresas medianas (50-500 empleados)
- Múltiples departamentos o equipos
- Productos/servicios diferenciados
- SLAs personalizados
- Soporte multiidioma básico
- Implementación: 3-4 semanas

---

## 📊 Diagrama del Modelo

```
                    ┌─────────────────┐
                    │   dim_customer  │
                    │─────────────────│
                    │ customer_key    │
                    │ name, email     │
                    │ segment_key(FK) │──→ dim_customer_segment
                    │ location        │
                    └────────┬────────┘
                             │
┌─────────────────┐          │          ┌─────────────────┐
│    dim_date     │          │          │    dim_agent    │
│─────────────────│          │          │─────────────────│
│ date_key (PK)   │          │          │ agent_key (PK)  │
│ date, year      │          │          │ name, email     │
│ month, quarter  │          │          │ team_key (FK) ──┼──→ dim_team
│ is_weekend      │          │          │ skill_level     │
└────────┬────────┘          │          └────────┬────────┘
         │                   │                   │
         │     ┌─────────────┴───────────────────┴───────┐
         │     │           fact_tickets                   │
         │     │──────────────────────────────────────────│
         └────→│ ticket_id (PK)                           │
               │ date_key (FK)                            │
               │ customer_key (FK)                        │
               │ submitter_user_id                        │
               │ submitter_email                          │
               │ submitter_name                           │
               │ agent_key (FK)                           │
               │ type_key (FK)         ┌──────────────┐   │
               │ priority_key (FK) ────┤              │   │
               │ status_key (FK)       │              │   │
               │ category_key (FK)     │              │   │
               │ product_key (FK)      │              │   │
               │ language_key (FK)     │              │   │
               │ channel_key (FK)      │              │   │
               │ ─────────────────     │              │   │
               │ created_at            │              │   │
               │ resolved_at           │              │   │
               │ resolution_time_hours │              │   │
               │ first_response_hours  │              │   │
               │ sla_breached          │              │   │
               └───────────┬───────────┴──────────────┘   │
                           │                              │
        ┌──────────────────┼──────────────────────────────┘
        │                  │
        │          ┌───────┴────────┐
        │          │                │
   ┌────▼─────┐  ┌▼──────────┐  ┌──▼─────────┐
   │dim_type  │  │dim_priority│  │ dim_status │
   │──────────│  │────────────│  │────────────│
   │type_key  │  │priority_key│  │ status_key │
   │name      │  │ name       │  │ name       │
   │          │  │ level (1-4)│  │ category   │
   └──────────┘  │ sla_hours  │  └────────────┘
                 └────────────┘

┌───────────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────┐
│ dim_category  │   │ dim_product  │   │dim_language │   │ dim_channel  │
│───────────────│   │──────────────│   │─────────────│   │──────────────│
│ category_key  │   │ product_key  │   │language_key │   │ channel_key  │
│ name          │   │ name         │   │ code (es/en)│   │ name         │
│ department    │   │ version      │   │ name        │   │ type         │
└───────────────┘   └──────────────┘   └─────────────┘   └──────────────┘

┌──────────────────────────┐       ┌────────────────────────────┐
│     ticket_text          │       │ fact_status_history        │
│──────────────────────────│       │────────────────────────────│
│ ticket_id (PK, FK)       │       │ history_id (PK)            │
│ subject                  │       │ ticket_id (FK)             │
│ description              │       │ status_key (FK)            │
│ solution                 │       │ agent_key (FK)             │
│ internal_notes           │       │ changed_at                 │
└──────────────────────────┘       │ duration_minutes           │
                                   └────────────────────────────┘
```

---

## 📋 Tabla de Hechos

### `fact_tickets`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticket_id` | INT (PK) | ID único del ticket |
| `date_key` | INT (FK) | Fecha de creación |
| `customer_key` | INT (FK) | Cliente que reporta |
| `submitter_user_id` | VARCHAR(100) | ID del usuario en el sistema |
| `submitter_email` | VARCHAR(255) | Email de quien crea |
| `submitter_name` | VARCHAR(255) | Nombre de quien reporta |
| `agent_key` | INT (FK) | Agente asignado |
| `type_key` | INT (FK) | Tipo de ticket |
| `priority_key` | INT (FK) | Prioridad |
| `status_key` | INT (FK) | Estado actual |
| `category_key` | INT (FK) | Categoría del problema |
| `product_key` | INT (FK) | Producto relacionado |
| `language_key` | INT (FK) | Idioma del ticket |
| `channel_key` | INT (FK) | Canal de entrada |
| `created_at` | TIMESTAMP | Fecha/hora creación |
| `resolved_at` | TIMESTAMP | Fecha/hora resolución |
| `closed_at` | TIMESTAMP | Fecha/hora cierre |
| `resolution_time_hours` | DECIMAL(8,2) | Tiempo de resolución |
| `first_response_hours` | DECIMAL(8,2) | Primera respuesta |
| `reopened_count` | INT | Veces reabierto |
| `sla_breached` | BOOLEAN | SLA violado |

---

## 📊 Dimensiones

### `dim_date`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `date_key` | INT (PK) | Clave (YYYYMMDD) |
| `date` | DATE | Fecha |
| `year` | INT | Año |
| `quarter` | INT | Trimestre |
| `month` | INT | Mes |
| `month_name` | VARCHAR(20) | Nombre mes |
| `week` | INT | Semana |
| `day` | INT | Día |
| `day_name` | VARCHAR(20) | Nombre día |
| `is_weekend` | BOOLEAN | Fin de semana |
| `is_holiday` | BOOLEAN | Día festivo |

### `dim_customer`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `customer_key` | INT (PK) | ID único |
| `customer_name` | VARCHAR(255) | Nombre |
| `email` | VARCHAR(255) | Email |
| `phone` | VARCHAR(50) | Teléfono |
| `company` | VARCHAR(255) | Empresa |
| `segment_key` | INT (FK) | Segmento cliente |
| `location` | VARCHAR(100) | Ubicación |
| `total_tickets` | INT | Tickets históricos |
| `is_vip` | BOOLEAN | Cliente VIP |
| `is_active` | BOOLEAN | Activo |

### `dim_customer_segment`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `segment_key` | INT (PK) | ID único |
| `segment_name` | VARCHAR(100) | Free, Standard, Premium, Enterprise |
| `sla_hours` | DECIMAL(5,2) | SLA del segmento |

### `dim_agent`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `agent_key` | INT (PK) | ID único |
| `agent_name` | VARCHAR(255) | Nombre |
| `email` | VARCHAR(255) | Email |
| `team_key` | INT (FK) | Equipo |
| `skill_level` | VARCHAR(50) | Junior, Mid, Senior |
| `is_active` | BOOLEAN | Activo |

### `dim_team`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `team_key` | INT (PK) | ID único |
| `team_name` | VARCHAR(100) | Soporte, IT, Ventas, etc. |
| `manager_name` | VARCHAR(255) | Nombre gerente |
| `specialization` | VARCHAR(100) | Especialización |

### `dim_ticket_type`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `type_key` | INT (PK) | ID único |
| `type_name` | VARCHAR(100) | Incident, Request, Problem |
| `default_sla_hours` | DECIMAL(5,2) | SLA por defecto |

### `dim_priority`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `priority_key` | INT (PK) | ID único |
| `priority_name` | VARCHAR(50) | Low, Medium, High, Critical |
| `priority_level` | INT | 1-4 |
| `sla_hours` | DECIMAL(5,2) | Tiempo SLA |

### `dim_status`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `status_key` | INT (PK) | ID único |
| `status_name` | VARCHAR(50) | New, In Progress, Resolved, Closed |
| `status_category` | VARCHAR(50) | Open, Closed |
| `is_final` | BOOLEAN | Estado final |

### `dim_category`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `category_key` | INT (PK) | ID único |
| `category_name` | VARCHAR(100) | Bug, Feature, Network, etc. |
| `department` | VARCHAR(100) | Departamento responsable |

### `dim_product`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_key` | INT (PK) | ID único |
| `product_name` | VARCHAR(255) | Nombre producto |
| `product_version` | VARCHAR(50) | Versión |
| `is_active` | BOOLEAN | Activo |

### `dim_language`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `language_key` | INT (PK) | ID único |
| `language_code` | VARCHAR(10) | es, en, fr, de |
| `language_name` | VARCHAR(100) | Español, English |

### `dim_channel`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `channel_key` | INT (PK) | ID único |
| `channel_name` | VARCHAR(50) | Email, Portal, Phone, Chat |
| `channel_type` | VARCHAR(50) | Digital, Voice |

---

## 📝 Tablas de Soporte

### `ticket_text`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticket_id` | INT (PK, FK) | ID ticket |
| `subject` | TEXT | Asunto |
| `description` | TEXT | Descripción |
| `solution` | TEXT | Solución |
| `internal_notes` | TEXT | Notas internas |

### `fact_status_history`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `history_id` | INT (PK) | ID único |
| `ticket_id` | INT (FK) | ID ticket |
| `status_key` | INT (FK) | Estado |
| `agent_key` | INT (FK) | Agente |
| `changed_at` | TIMESTAMP | Fecha cambio |
| `duration_minutes` | DECIMAL(10,2) | Tiempo en estado |

---

## 📈 Consultas SQL

### 1. Dashboard Ejecutivo

```sql
-- KPIs principales
SELECT 
    COUNT(*) as total_tickets,
    SUM(CASE WHEN s.status_category = 'Open' THEN 1 ELSE 0 END) as tickets_abiertos,
    SUM(CASE WHEN s.status_category = 'Closed' THEN 1 ELSE 0 END) as tickets_cerrados,
    AVG(CASE WHEN resolved_at IS NOT NULL THEN resolution_time_hours END) as avg_resolution_hours,
    SUM(CASE WHEN sla_breached = TRUE THEN 1 ELSE 0 END) as sla_breaches,
    ROUND(100.0 * SUM(CASE WHEN sla_breached = FALSE THEN 1 ELSE 0 END) / COUNT(*), 2) as sla_compliance
FROM fact_tickets t
JOIN dim_status s ON t.status_key = s.status_key
WHERE t.created_at >= CURRENT_DATE - INTERVAL '30 days';
```

### 2. Tickets por Categoría y Producto

```sql
SELECT 
    c.category_name,
    p.product_name,
    COUNT(*) as total_tickets,
    AVG(t.resolution_time_hours) as avg_resolution,
    SUM(CASE WHEN t.sla_breached = TRUE THEN 1 ELSE 0 END) as sla_breaches
FROM fact_tickets t
JOIN dim_category c ON t.category_key = c.category_key
JOIN dim_product p ON t.product_key = p.product_key
WHERE t.created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY c.category_name, p.product_name
ORDER BY total_tickets DESC;
```

### 3. Performance por Equipo

```sql
SELECT 
    tm.team_name,
    COUNT(DISTINCT a.agent_key) as num_agentes,
    COUNT(*) as tickets_resueltos,
    AVG(t.resolution_time_hours) as avg_resolution,
    AVG(t.first_response_hours) as avg_first_response,
    SUM(CASE WHEN t.sla_breached = TRUE THEN 1 ELSE 0 END) as sla_breaches
FROM fact_tickets t
JOIN dim_agent a ON t.agent_key = a.agent_key
JOIN dim_team tm ON a.team_key = tm.team_key
WHERE t.resolved_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY tm.team_name
ORDER BY tickets_resueltos DESC;
```

### 4. Análisis por Segmento de Cliente

```sql
SELECT 
    cs.segment_name,
    COUNT(*) as total_tickets,
    AVG(t.resolution_time_hours) as avg_resolution,
    cs.sla_hours as sla_target,
    SUM(CASE WHEN t.sla_breached = TRUE THEN 1 ELSE 0 END) as breaches,
    ROUND(100.0 * SUM(CASE WHEN t.sla_breached = FALSE THEN 1 ELSE 0 END) / COUNT(*), 2) as compliance_rate
FROM fact_tickets t
JOIN dim_customer c ON t.customer_key = c.customer_key
JOIN dim_customer_segment cs ON c.segment_key = cs.segment_key
WHERE t.created_at >= CURRENT_DATE - INTERVAL '60 days'
GROUP BY cs.segment_name, cs.sla_hours
ORDER BY total_tickets DESC;
```

### 5. Tickets por Canal e Idioma

```sql
SELECT 
    ch.channel_name,
    l.language_name,
    COUNT(*) as total_tickets,
    AVG(t.first_response_hours) as avg_first_response,
    AVG(t.resolution_time_hours) as avg_resolution
FROM fact_tickets t
JOIN dim_channel ch ON t.channel_key = ch.channel_key
JOIN dim_language l ON t.language_key = l.language_key
WHERE t.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY ch.channel_name, l.language_name
ORDER BY total_tickets DESC;
```

### 6. Historial de Cambios de Estado

```sql
SELECT 
    t.ticket_id,
    tt.subject,
    s.status_name,
    a.agent_name,
    h.changed_at,
    h.duration_minutes
FROM fact_status_history h
JOIN fact_tickets t ON h.ticket_id = t.ticket_id
JOIN dim_status s ON h.status_key = s.status_key
LEFT JOIN dim_agent a ON h.agent_key = a.agent_key
LEFT JOIN ticket_text tt ON t.ticket_id = tt.ticket_id
WHERE t.ticket_id = 12345
ORDER BY h.changed_at ASC;
```

### 7. Top Usuarios Reportadores

```sql
SELECT 
    submitter_email,
    submitter_name,
    COUNT(*) as total_tickets,
    SUM(CASE WHEN s.status_category = 'Open' THEN 1 ELSE 0 END) as tickets_abiertos,
    AVG(resolution_time_hours) as avg_resolution
FROM fact_tickets t
JOIN dim_status s ON t.status_key = s.status_key
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY submitter_email, submitter_name
HAVING COUNT(*) > 5
ORDER BY total_tickets DESC
LIMIT 20;
```

---

## 🔄 Proceso ETL

```
┌──────────────────────────────────────────────────────┐
│         ETL MEDIUM - PROCESO COMPLETO                │
└──────────────────────────────────────────────────────┘

   1. Recibir Ticket
      • Email, Portal, API, Chat
      • Capturar submitter info
         │
         ▼
   2. Detección Automática
      • Idioma → language_key
      • Producto (del asunto) → product_key
      • Categoría (keywords) → category_key
      • Canal → channel_key
         │
         ▼
   3. Lookup/Upsert Customer
      • Buscar por email
      • Si existe → customer_key
      • Si no → INSERT customer
      • Verificar segmento
         │
         ▼
   4. Asignación Inteligente
      • Prioridad (reglas + keywords)
      • Tipo de ticket
      • Equipo (por categoría)
      • Agente (carga trabajo + skill)
         │
         ▼
   5. Validación SLA
      • segment_key → sla_hours
      • priority_key → sla_hours
      • Calcular deadline
         │
         ▼
   6. INSERT fact_tickets
      • Todos los FKs
      • submitter info
      • created_at = NOW()
      • status_key = 1 (New)
         │
         ▼
   7. INSERT ticket_text
      • subject, description
         │
         ▼
   8. INSERT status_history
      • Registro inicial
         │
         ▼
   9. Notificaciones
      • Email a customer
      • Alerta a agente
      • Dashboard update
         │
         ▼
  10. ✓ Ticket Creado
```

---

## ✅ Ventajas del Modelo Medium

1. **Balance perfecto**: Funcionalidad sin complejidad excesiva
2. **Multiproducto**: Análisis por producto/servicio
3. **Multiequipo**: Gestión de varios departamentos
4. **SLAs personalizados**: Por segmento de cliente
5. **Multicanal**: Email, portal, phone, chat
6. **Multiidioma básico**: Español, inglés, francés, alemán
7. **Historial de cambios**: Trazabilidad completa
8. **Captura de creador**: submitter_email, submitter_name, submitter_user_id
9. **Análisis avanzado**: Más dimensiones para reporting
10. **Escalable**: Migración fácil a modelo Expert

---

## 📊 KPIs y Métricas

### Dashboard Recomendado

1. **Volumen de Tickets**
   - Total por día/semana/mes
   - Por categoría
   - Por producto
   - Por canal

2. **Tiempos de Respuesta**
   - Primera respuesta promedio
   - Tiempo de resolución por prioridad
   - Tiempo de resolución por equipo

3. **Cumplimiento SLA**
   - % de cumplimiento global
   - Por segmento de cliente
   - Por equipo
   - Tendencia mensual

4. **Distribución**
   - Tickets por agente
   - Tickets por equipo
   - Tickets por categoría
   - Tickets por idioma

5. **Calidad**
   - Tickets reabiertos
   - Tiempo promedio en cada estado
   - Escalaciones

---

## 🚀 Implementación

### Fases del Proyecto

**Fase 1: Setup (Semana 1)**
- Crear base de datos
- Ejecutar scripts DDL
- Poblar tablas de dimensiones
- Configurar usuarios

**Fase 2: ETL (Semana 2)**
- Desarrollar parsers (email, web)
- Lógica de detección automática
- Reglas de asignación
- Testing de integración

**Fase 3: Dashboard (Semana 3)**
- Crear vistas SQL
- Dashboard básico
- Reportes automáticos
- Alertas

**Fase 4: Testing y Deploy (Semana 4)**
- Testing con usuarios reales
- Ajustes y optimización
- Training
- Go-live

---

## 🎯 Cuándo Migrar al Modelo Expert

Migra al modelo Expert cuando necesites:
- Análisis de sentimiento avanzado
- Predicción de escalación con ML
- Múltiples ubicaciones geográficas
- Industrias diferenciadas
- Jerarquías complejas (categorías multinivel)
- Knowledge base integrada
- Costos por ticket
- Social media integration
- Más de 10,000 tickets/mes

---

## 📝 Equipo Recomendado

- 1-2 desarrolladores backend
- 1 desarrollador frontend
- 1 DBA/DevOps
- 1 QA
- 1 Product Owner
- **Tiempo: 3-4 semanas**

---

## 🎉 Conclusión

El modelo Medium ofrece el mejor balance entre:
- ✅ Funcionalidad completa para análisis
- ✅ Simplicidad en mantenimiento
- ✅ Escalabilidad probada
- ✅ ROI rápido (3-4 semanas)
- ✅ Captura completa de quién crea tickets

**¡Perfecto para empresas en crecimiento!** 🚀
