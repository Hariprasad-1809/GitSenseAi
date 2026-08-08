-- Enable the pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID extension for project identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sessions Table
CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Projects Table (Belongs to session, max 1 project per session via UNIQUE constraint)
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    session_id UUID UNIQUE NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    repo_url TEXT,
    status TEXT NOT NULL DEFAULT 'queued', -- queued, processing, completed, failed
    files_processed INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    current_file TEXT DEFAULT '',
    error TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Files Table (for general repository metadata lookup and incremental indexing)
CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    size_bytes BIGINT DEFAULT 0,
    file_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, file_path)
);

-- Chunks Table with Vector Embedding (bge-small-en-v1.5 has 384 dimensions)
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    symbol_name TEXT,
    symbol_type TEXT,
    parent_class TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    chunking_method TEXT NOT NULL, -- ast, md, fallback
    metadata JSONB DEFAULT '{}'::jsonb,
    fts_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- Chat Q&A History Table (belongs to both session and project)
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB NOT NULL, -- JSON list of citation objects
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Intelligence Cache Table (for precomputed & lazily generated repository intelligence)
CREATE TABLE IF NOT EXISTS intelligence_cache (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cache_key TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, cache_key)
);

-- Create HNSW index for Pgvector Cosine Similarity
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);

-- Create GIN index for PostgreSQL Full-Text Search
CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin (fts_vector);

-- Secondary indexing to speed up queries
CREATE INDEX IF NOT EXISTS chunks_project_id_idx ON chunks (project_id);
CREATE INDEX IF NOT EXISTS files_project_id_idx ON files (project_id);
CREATE INDEX IF NOT EXISTS chat_history_project_id_idx ON chat_history (project_id);
CREATE INDEX IF NOT EXISTS chat_history_session_id_idx ON chat_history (session_id);
CREATE INDEX IF NOT EXISTS intelligence_cache_project_key_idx ON intelligence_cache (project_id, cache_key);

