-- =============================================================================
-- Migración 001: Esquema Base Inicial (Reflejo exacto del ERD de Supabase)
-- =============================================================================

-- 1. Tabla de Usuarios (users)
CREATE TABLE IF NOT EXISTS public.users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    refresh_token_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_refresh_hash ON public.users(refresh_token_hash);

-- 2. Tabla de Bases de Datos / Archivos (files)
CREATE TABLE IF NOT EXISTS public.files (
    id BIGSERIAL PRIMARY KEY,
    owner_user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    size_bytes BIGINT,
    sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_encrypted BOOLEAN NOT NULL DEFAULT TRUE,
    enc_version TEXT NOT NULL DEFAULT 'aes-256-gcm-v1',
    enc_nonce TEXT,
    key_ref TEXT,
    api_password_hash TEXT,
    share_code TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_files_owner ON public.files(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_files_share_code ON public.files(share_code);

-- 3. Tabla de Acceso y Jerarquía de Usuarios (user_files)
CREATE TABLE IF NOT EXISTS public.user_files (
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    file_id BIGINT NOT NULL REFERENCES public.files(id) ON DELETE CASCADE,
    is_owner BOOLEAN NOT NULL DEFAULT FALSE,
    invited_by BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
    invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_user_files_user ON public.user_files(user_id);
CREATE INDEX IF NOT EXISTS idx_user_files_file ON public.user_files(file_id);
CREATE INDEX IF NOT EXISTS idx_user_files_invited_by ON public.user_files(invited_by);

-- 4. Tabla de Consultas Guardadas (saved_queries)
CREATE TABLE IF NOT EXISTS public.saved_queries (
    id BIGSERIAL PRIMARY KEY,
    file_id BIGINT NOT NULL REFERENCES public.files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    query_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_queries_file ON public.saved_queries(file_id);

-- 5. Tabla de Almacenamiento de Blobs SQLite (file_storage_blobs)
CREATE TABLE IF NOT EXISTS public.file_storage_blobs (
    storage_path TEXT PRIMARY KEY,
    encrypted_blob BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
