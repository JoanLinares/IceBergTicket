# Modelo Snowflake BÁSICO - Sistema de Tickets

## 🎯 Propósito

Modelo **simplificado** diseñado para **pequeñas empresas** o equipos que comienzan con la gestión de tickets. Incluye solo las dimensiones y métricas esenciales para empezar rápido.

**Ideal para:**
- Startups y pequeñas empresas (1-50 empleados)
- Equipos que empiezan con ticketing estructurado
- Implementación rápida (1-2 semanas)
- Migración desde sistemas simples (Excel, email)

---

## 📊 Diagrama del Modelo

```
                 ┌─────────────────┐
                 │    dim_date     │
                 │─────────────────│
                 │ date_key (PK)   │
                 │ date            │
                 │ year, month     │
                 │ day, day_name   │
                 └────────┬────────┘
                          │
                          │
      ┌───────────────────┼───────────────────┐
      │                   │                   │
┌─────▼──────┐   ┌────────▼────────┐   ┌─────▼──────┐
│dim_customer│   │  fact_tickets   │   │ dim_agent  │
│────────────│   │─────────────────│   │────────────│
│customer_key│←──│ ticket_id (PK)  │──→│ agent_key  │
│name        │   │ date_key (FK)   │   │ name       │
│email       │   │ customer_key(FK)│   │ email      │
└────────────┘   │ agent_key (FK)  │   │ team       │
                 │ priority_key(FK)│   └────────────┘
                 │ status_key (FK) │
      ┌──────────│ ─────────────── │
      │          │ submitter_email │
      │          │ submitter_name  │
      │          │ created_at      │
      │          │ resolved_at     │
      │          │ resolution_time │
      │          └────────┬────────┘
      │                   │
┌─────▼──────┐   ┌────────▼────────┐
│dim_priority│   │   dim_status    │
│────────────│   │─────────────────│
│priority_key│   │ status_key (PK) │
│name        │   │ name            │
│level (1-3) │   │ category        │
└────────────┘   └─────────────────┘

┌──────────────────────────┐
│     ticket_text          │
│──────────────────────────│
│ ticket_id (PK, FK)       │
│ subject                  │
│ description              │
│ solution                 │
└──────────────────────────┘
```

---

## 📋 Tablas del Modelo

### Tabla de Hechos

#### `fact_tickets`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticket_id` | INT (PK) | ID único del ticket |
| `date_key` | INT (FK) | Fecha de creación |
| `customer_key` | INT (FK) | Cliente que reporta |
| `agent_key` | INT (FK) | Agente asignado |
| `priority_key` | INT (FK) | Prioridad del ticket |
| `status_key` | INT (FK) | Estado actual |
| `submitter_email` | VARCHAR(255) | Email de quien crea el ticket |
| `submitter_name` | VARCHAR(255) | Nombre de quien reporta |
| `created_at` | TIMESTAMP | Fecha/hora de creación |
| `resolved_at` | TIMESTAMP | Fecha/hora de resolución |
| `closed_at` | TIMESTAMP | Fecha/hora de cierre |
| `resolution_time_hours` | DECIMAL(8,2) | Tiempo de resolución en horas |
| `first_response_hours` | DECIMAL(8,2) | Tiempo de primera respuesta |

---

### Dimensiones

#### `dim_date`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `date_key` | INT (PK) | Clave (YYYYMMDD) |
| `date` | DATE | Fecha completa |
| `year` | INT | Año |
| `month` | INT | Mes (1-12) |
| `month_name` | VARCHAR(20) | Nombre del mes |
| `day` | INT | Día del mes |
| `day_name` | VARCHAR(20) | Nombre del día |
| `is_weekend` | BOOLEAN | Fin de semana |

#### `dim_customer`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `customer_key` | INT (PK) | ID único |
| `customer_name` | VARCHAR(255) | Nombre completo |
| `email` | VARCHAR(255) | Email |
| `phone` | VARCHAR(50) | Teléfono |
| `company` | VARCHAR(255) | Empresa |
| `is_active` | BOOLEAN | Cliente activo |

#### `dim_agent`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `agent_key` | INT (PK) | ID único |
| `agent_name` | VARCHAR(255) | Nombre del agente |
| `email` | VARCHAR(255) | Email |
| `team` | VARCHAR(100) | Equipo (Soporte, Ventas, IT) |
| `is_active` | BOOLEAN | Agente activo |

#### `dim_priority`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `priority_key` | INT (PK) | ID único |
| `priority_name` | VARCHAR(50) | Baja, Media, Alta |
| `priority_level` | INT | Nivel numérico (1-3) |
| `target_hours` | DECIMAL(5,2) | Tiempo objetivo resolución |

#### `dim_status`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `status_key` | INT (PK) | ID único |
| `status_name` | VARCHAR(50) | Nuevo, En Proceso, Resuelto, Cerrado |
| `status_category` | VARCHAR(50) | Abierto, Cerrado |
| `is_final` | BOOLEAN | Es estado final |

---

### Tabla de Texto

#### `ticket_text`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ticket_id` | INT (PK, FK) | ID del ticket |
| `subject` | TEXT | Asunto |
| `description` | TEXT | Descripción del problema |
| `solution` | TEXT | Solución aplicada |

---

## 📈 Consultas Básicas

### 1. Tickets Abiertos

```sql
SELECT 
    t.ticket_id,
    c.customer_name,
    a.agent_name,
    p.priority_name,
    s.status_name,
    t.created_at,
    tt.subject
FROM fact_tickets t
JOIN dim_customer c ON t.customer_key = c.customer_key
JOIN dim_agent a ON t.agent_key = a.agent_key
JOIN dim_priority p ON t.priority_key = p.priority_key
JOIN dim_status s ON t.status_key = s.status_key
LEFT JOIN ticket_text tt ON t.ticket_id = tt.ticket_id
WHERE s.status_category = 'Abierto'
ORDER BY p.priority_level DESC, t.created_at ASC;
```

### 2. Tickets por Prioridad

```sql
SELECT 
    p.priority_name,
    COUNT(*) as total_tickets,
    AVG(t.resolution_time_hours) as avg_resolution_hours
FROM fact_tickets t
JOIN dim_priority p ON t.priority_key = p.priority_key
WHERE t.resolved_at IS NOT NULL
GROUP BY p.priority_name
ORDER BY p.priority_level DESC;
```

### 3. Performance de Agentes

```sql
SELECT 
    a.agent_name,
    a.team,
    COUNT(*) as tickets_resueltos,
    AVG(t.resolution_time_hours) as promedio_horas,
    AVG(t.first_response_hours) as promedio_primera_respuesta
FROM fact_tickets t
JOIN dim_agent a ON t.agent_key = a.agent_key
WHERE t.resolved_at >= CURRENT_DATE - INTERVAL '30 days'
  AND t.resolved_at IS NOT NULL
GROUP BY a.agent_name, a.team
ORDER BY tickets_resueltos DESC;
```

### 4. Tickets por Mes

```sql
SELECT 
    d.year,
    d.month_name,
    COUNT(*) as total_tickets,
    SUM(CASE WHEN s.status_category = 'Cerrado' THEN 1 ELSE 0 END) as tickets_cerrados,
    AVG(t.resolution_time_hours) as avg_resolution_hours
FROM fact_tickets t
JOIN dim_date d ON t.date_key = d.date_key
JOIN dim_status s ON t.status_key = s.status_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year DESC, d.month DESC;
```

### 5. Top Clientes con Más Tickets

```sql
SELECT 
    c.customer_name,
    c.company,
    c.email,
    COUNT(*) as total_tickets,
    AVG(t.resolution_time_hours) as avg_resolution
FROM fact_tickets t
JOIN dim_customer c ON t.customer_key = c.customer_key
WHERE t.created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY c.customer_name, c.company, c.email
ORDER BY total_tickets DESC
LIMIT 10;
```

---

## 🚀 Script de Creación SQL

```sql
-- Crear dimensión fecha
CREATE TABLE dim_date (
    date_key INT PRIMARY KEY,
    date DATE NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day INT NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

-- Crear dimensión cliente
CREATE TABLE dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    company VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear dimensión agente
CREATE TABLE dim_agent (
    agent_key SERIAL PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    team VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    hired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear dimensión prioridad
CREATE TABLE dim_priority (
    priority_key SERIAL PRIMARY KEY,
    priority_name VARCHAR(50) NOT NULL,
    priority_level INT NOT NULL CHECK (priority_level BETWEEN 1 AND 3),
    target_hours DECIMAL(5,2) NOT NULL
);

-- Insertar prioridades por defecto
INSERT INTO dim_priority (priority_name, priority_level, target_hours) VALUES
('Baja', 1, 48.00),
('Media', 2, 24.00),
('Alta', 3, 4.00);

-- Crear dimensión estado
CREATE TABLE dim_status (
    status_key SERIAL PRIMARY KEY,
    status_name VARCHAR(50) NOT NULL,
    status_category VARCHAR(50) NOT NULL,
    is_final BOOLEAN DEFAULT FALSE
);

-- Insertar estados por defecto
INSERT INTO dim_status (status_name, status_category, is_final) VALUES
('Nuevo', 'Abierto', FALSE),
('En Proceso', 'Abierto', FALSE),
('Resuelto', 'Cerrado', TRUE),
('Cerrado', 'Cerrado', TRUE);

-- Crear tabla de hechos
CREATE TABLE fact_tickets (
    ticket_id SERIAL PRIMARY KEY,
    date_key INT NOT NULL,
    customer_key INT NOT NULL,
    agent_key INT,
    priority_key INT NOT NULL,
    status_key INT NOT NULL,
    submitter_email VARCHAR(255) NOT NULL,
    submitter_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    closed_at TIMESTAMP,
    resolution_time_hours DECIMAL(8,2),
    first_response_hours DECIMAL(8,2),
    
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
    FOREIGN KEY (agent_key) REFERENCES dim_agent(agent_key),
    FOREIGN KEY (priority_key) REFERENCES dim_priority(priority_key),
    FOREIGN KEY (status_key) REFERENCES dim_status(status_key)
);

-- Crear tabla de texto
CREATE TABLE ticket_text (
    ticket_id INT PRIMARY KEY,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    solution TEXT,
    
    FOREIGN KEY (ticket_id) REFERENCES fact_tickets(ticket_id) ON DELETE CASCADE
);

-- Índices para mejorar performance
CREATE INDEX idx_tickets_date ON fact_tickets(date_key);
CREATE INDEX idx_tickets_customer ON fact_tickets(customer_key);
CREATE INDEX idx_tickets_agent ON fact_tickets(agent_key);
CREATE INDEX idx_tickets_status ON fact_tickets(status_key);
CREATE INDEX idx_tickets_priority ON fact_tickets(priority_key);
CREATE INDEX idx_tickets_created ON fact_tickets(created_at);
CREATE INDEX idx_tickets_submitter_email ON fact_tickets(submitter_email);
```

---

## 🔄 Proceso ETL Simplificado

```
┌──────────────────────────────────────────────────────┐
│              ETL BÁSICO - CREAR TICKET               │
└──────────────────────────────────────────────────────┘

   1. Recibir ticket (email/formulario web)
         │
         ▼
   2. Extraer información
      • Email del remitente → submitter_email
      • Nombre → submitter_name
      • Asunto → subject
      • Descripción → description
         │
         ▼
   3. Buscar o crear customer
      • Si email existe → usar customer_key
      • Si no existe → INSERT nuevo customer
         │
         ▼
   4. Asignar valores por defecto
      • priority_key → 2 (Media)
      • status_key → 1 (Nuevo)
      • agent_key → NULL (auto-assign después)
      • date_key → YYYYMMDD de hoy
         │
         ▼
   5. INSERT en fact_tickets
      • Calcular date_key
      • Guardar submitter_email y submitter_name
      • created_at = NOW()
         │
         ▼
   6. INSERT en ticket_text
      • subject
      • description
         │
         ▼
   7. ✓ Ticket creado
      • Enviar notificación
      • Auto-asignar agente
```

---

## ✅ Ventajas del Modelo Básico

1. **Simplicidad**: Solo 5 dimensiones + 1 tabla de hechos
2. **Rápido de implementar**: 1-2 semanas
3. **Fácil de entender**: Estructura intuitiva
4. **Bajo mantenimiento**: Menos tablas = menos complejidad
5. **Captura lo esencial**: 
   - ¿Quién reportó? (submitter_email, submitter_name)
   - ¿Cuándo? (date, created_at)
   - ¿Qué prioridad? (priority)
   - ¿Quién lo maneja? (agent)
   - ¿En qué estado? (status)
6. **Escalable**: Fácil migrar a modelo Medium después

---

## 📊 KPIs Básicos

### Dashboard Esencial

```sql
-- Total tickets por estado
SELECT 
    s.status_name,
    COUNT(*) as total
FROM fact_tickets t
JOIN dim_status s ON t.status_key = s.status_key
GROUP BY s.status_name;

-- Tiempo promedio de resolución
SELECT 
    AVG(resolution_time_hours) as avg_hours,
    MIN(resolution_time_hours) as min_hours,
    MAX(resolution_time_hours) as max_hours
FROM fact_tickets
WHERE resolved_at IS NOT NULL;

-- Tickets creados esta semana
SELECT 
    d.day_name,
    COUNT(*) as tickets
FROM fact_tickets t
JOIN dim_date d ON t.date_key = d.date_key
WHERE t.created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY d.day_name, d.date
ORDER BY d.date;

-- Carga de trabajo por agente
SELECT 
    a.agent_name,
    COUNT(*) as tickets_asignados,
    SUM(CASE WHEN s.status_category = 'Abierto' THEN 1 ELSE 0 END) as tickets_abiertos
FROM fact_tickets t
JOIN dim_agent a ON t.agent_key = a.agent_key
JOIN dim_status s ON t.status_key = s.status_key
GROUP BY a.agent_name
ORDER BY tickets_abiertos DESC;
```

---

## 🎯 Cuándo Migrar al Modelo Medium

Considera migrar cuando:
- Tienes más de 1000 tickets/mes
- Necesitas categorizar tickets (IT, Ventas, Soporte, etc.)
- Quieres analizar por producto/servicio
- Necesitas SLAs diferenciados
- Tienes múltiples equipos o departamentos
- Requieres análisis de idioma
- Necesitas tracking detallado de cambios de estado

---

## 📝 Notas de Implementación

**Tecnologías recomendadas:**
- Base de datos: PostgreSQL, MySQL
- Backend: Python Flask, Node.js Express
- Frontend: HTML/CSS simple, React básico
- ETL: Scripts Python con pandas

**Tiempo estimado de setup:**
- Base de datos: 1 día
- Scripts ETL: 2-3 días
- Dashboard básico: 2-3 días
- Testing: 2 días
- **Total: 1-2 semanas**

**Equipo mínimo:**
- 1 desarrollador full-stack
- 1 QA (part-time)

---

## 🚀 Próximos Pasos

1. Instalar base de datos
2. Ejecutar script de creación
3. Poblar dim_date (tabla calendario)
4. Crear usuarios de prueba en dim_customer y dim_agent
5. Crear formulario web de tickets
6. Implementar ETL básico
7. Dashboard con consultas SQL
8. Probar con tickets reales

**¡Listo para empezar!** 🎉
