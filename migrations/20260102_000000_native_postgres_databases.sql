-- =============================================================================
-- Migración 002: Transición a Bases de Datos Nativas en PostgreSQL
-- =============================================================================
-- Propósito:
--   1. Adaptar la tabla `files` para almacenar bases de datos nativas en PostgreSQL
--      asociadas a su ID y a los usuarios/jerarquía existente (owner, invited_by, etc.).
--   2. Añadir soporte para MinIO (almacenamiento de datasets originales y backups).
--   3. Crear la estructura dimensional analítica en PostgreSQL para no depender de SQLite.
-- =============================================================================

-- 1. Actualizar la tabla `files` con campos para gestión nativa y MinIO
ALTER TABLE public.files 
    ADD COLUMN IF NOT EXISTS storage_backend TEXT NOT NULL DEFAULT 'postgres', -- 'postgres', 'sqlite_blob', 'minio'
    ADD COLUMN IF NOT EXISTS db_schema_name TEXT,                             -- ej: 'dataset_15' para aislamiento por esquema
    ADD COLUMN IF NOT EXISTS minio_bucket TEXT,                                -- bucket donde se guarda el dataset original
    ADD COLUMN IF NOT EXISTS minio_object_key TEXT,                            -- ruta del objeto en MinIO
    ALTER COLUMN storage_path DROP NOT NULL,
    ALTER COLUMN is_encrypted SET DEFAULT FALSE;

-- 2. Función helper para inicializar el esquema analítico de un dataset específico
-- Permite que cada dataset (file_id) tenga su propio espacio aislado en PostgreSQL:
-- CREATE SCHEMA IF NOT EXISTS dataset_<id>;
CREATE OR REPLACE FUNCTION public.create_dataset_dw_schema(p_file_id BIGINT, p_level TEXT)
RETURNS TEXT AS $$
DECLARE
    v_schema TEXT;
BEGIN
    v_schema := 'dataset_' || p_file_id;
    
    -- Crear el esquema privado para este dataset
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS ' || quote_ident(v_schema);
    
    -- Tabla dim_date
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_date (
        date_key BIGINT PRIMARY KEY,
        date TEXT,
        year INTEGER,
        quarter INTEGER,
        month INTEGER,
        month_name TEXT,
        day INTEGER,
        day_of_week INTEGER,
        day_name TEXT,
        is_weekend INTEGER,
        fiscal_year INTEGER
    )';

    -- Tabla dim_customer
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_customer (
        customer_key BIGSERIAL PRIMARY KEY,
        customer_name TEXT,
        email TEXT UNIQUE
    )';

    -- Tabla dim_agent
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_agent (
        agent_key BIGSERIAL PRIMARY KEY,
        agent_name TEXT UNIQUE,
        team TEXT
    )';

    -- Tabla dim_priority
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_priority (
        priority_key BIGSERIAL PRIMARY KEY,
        priority_name TEXT UNIQUE
    )';

    -- Tabla dim_status
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_status (
        status_key BIGSERIAL PRIMARY KEY,
        status_name TEXT UNIQUE
    )';

    -- Tabla dim_language
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_language (
        language_key BIGSERIAL PRIMARY KEY,
        language_code TEXT UNIQUE,
        language_name TEXT
    )';

    -- Dimensiones específicas según nivel
    IF p_level IN ('MEDIUM', 'PRO') THEN
        EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_ticket_type (
            type_key BIGSERIAL PRIMARY KEY,
            type_name TEXT UNIQUE
        )';
    END IF;

    IF p_level = 'PRO' THEN
        EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_queue (
            queue_key BIGSERIAL PRIMARY KEY,
            queue_name TEXT UNIQUE
        )';
        EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.dim_tag (
            tag_key BIGSERIAL PRIMARY KEY,
            tag_name TEXT UNIQUE
        )';
    END IF;

    -- Tabla de Hechos: fact_tickets
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.fact_tickets (
        ticket_id BIGSERIAL PRIMARY KEY,
        date_key BIGINT REFERENCES ' || quote_ident(v_schema) || '.dim_date(date_key),
        customer_key BIGINT REFERENCES ' || quote_ident(v_schema) || '.dim_customer(customer_key),
        agent_key BIGINT REFERENCES ' || quote_ident(v_schema) || '.dim_agent(agent_key),
        type_key BIGINT,
        priority_key BIGINT REFERENCES ' || quote_ident(v_schema) || '.dim_priority(priority_key),
        queue_key BIGINT,
        language_key BIGINT REFERENCES ' || quote_ident(v_schema) || '.dim_language(language_key),
        status_key BIGINT REFERENCES ' || quote_ident(v_schema) || '.dim_status(status_key),
        created_at BIGINT,
        pred_type TEXT,
        pred_language TEXT,
        word_count_subject INTEGER,
        word_count_body INTEGER
    )';

    -- Tabla de Texto Desacoplado: ticket_text
    EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.ticket_text (
        ticket_id BIGINT PRIMARY KEY,
        subject TEXT,
        body TEXT,
        answer TEXT
    )';

    -- Puente N:M para tags (Nivel PRO)
    IF p_level = 'PRO' THEN
        EXECUTE 'CREATE TABLE IF NOT EXISTS ' || quote_ident(v_schema) || '.bridge_ticket_tags (
            ticket_id BIGINT REFERENCES ' || quote_ident(v_schema) || '.fact_tickets(ticket_id) ON DELETE CASCADE,
            tag_key BIGINT REFERENCES ' || quote_ident(v_schema) || '.dim_tag(tag_key) ON DELETE CASCADE,
            tag_order INTEGER,
            PRIMARY KEY (ticket_id, tag_key)
        )';
    END IF;

    -- Actualizar el registro en files con el nombre del esquema
    UPDATE public.files 
    SET db_schema_name = v_schema, storage_backend = 'postgres'
    WHERE id = p_file_id;

    RETURN v_schema;
END;
$$ LANGUAGE plpgsql;
