-- PostgreSQL initialization script for Newbee Notebook
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create chat_sessions table for conversation management
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create chat_messages table for message storage
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('chat', 'ask', 'conclude', 'explain')),
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create index on session_id for faster message queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);

-- Create index on mode for filtering by mode type
CREATE INDEX IF NOT EXISTS idx_chat_messages_mode ON chat_messages(mode);

-- Create index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

-- =============================================================================
-- Core domain tables for Notebook + Library system
-- =============================================================================

-- Library (singleton record expected)
CREATE TABLE IF NOT EXISTS library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Notebooks
CREATE TABLE IF NOT EXISTS notebooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    session_count INTEGER DEFAULT 0,
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notebooks_created_at ON notebooks(created_at);
CREATE INDEX IF NOT EXISTS idx_notebooks_updated_at ON notebooks(updated_at);

-- Documents (library-first model)
-- All documents belong to Library. Notebook association is managed via notebook_document_refs.
-- notebook_id column is retained for backward compatibility but should not be used in new code.
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    library_id UUID NOT NULL REFERENCES library(id),
    notebook_id UUID REFERENCES notebooks(id),
    title VARCHAR(500) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(1000),
    url VARCHAR(2000),
    status VARCHAR(20) DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'pending', 'processing', 'converted', 'completed', 'failed')),
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    file_size INTEGER DEFAULT 0,
    content_path VARCHAR(1000),
    content_format VARCHAR(50) DEFAULT 'markdown',
    content_size INTEGER DEFAULT 0,
    error_message TEXT,
    processing_stage VARCHAR(64),
    stage_updated_at TIMESTAMP,
    processing_meta TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_library_id ON documents(library_id);
CREATE INDEX IF NOT EXISTS idx_documents_notebook_id ON documents(notebook_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_stage_updated_at ON documents(stage_updated_at);

-- Backfill additive columns for existing volumes where table already exists
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title VARCHAR(500),
    message_count INTEGER NOT NULL DEFAULT 0,
    context_summary TEXT,
    include_ec_context BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_notebook_id ON sessions(notebook_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);

-- Backfill additive columns for existing volumes where table already exists
ALTER TABLE IF EXISTS sessions ADD COLUMN IF NOT EXISTS include_ec_context BOOLEAN NOT NULL DEFAULT FALSE;

-- Notebook-document soft references
CREATE TABLE IF NOT EXISTS notebook_document_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_notebook_document UNIQUE (notebook_id, document_id)
);
CREATE INDEX IF NOT EXISTS idx_notebook_document_refs_notebook_id
    ON notebook_document_refs(notebook_id);
CREATE INDEX IF NOT EXISTS idx_notebook_document_refs_document_id
    ON notebook_document_refs(document_id);

-- Application settings (runtime key-value overrides for model/config switches)
CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(128) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- References (source tracing; chunk_id stored as LlamaIndex node id text)
CREATE TABLE IF NOT EXISTS "references" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id INTEGER,
    chunk_id VARCHAR(100),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    quoted_text TEXT,
    context TEXT,
    document_title VARCHAR(500),
    is_source_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_references_session_id ON "references"(session_id);
CREATE INDEX IF NOT EXISTS idx_references_document_id ON "references"(document_id);
CREATE INDEX IF NOT EXISTS idx_references_created_at ON "references"(created_at);

-- Messages stored alongside sessions (business tables)
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('chat','ask','conclude','explain')),
    role VARCHAR(20) NOT NULL CHECK (role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- ============================================================================
-- Multi-Provider Vector Store Tables
-- ============================================================================
-- Note: These tables are created by LlamaIndex automatically when building indexes.
-- The definitions below are for reference only and match the expected schema.
--
-- LlamaIndex automatically prefixes table names with 'data_', so:
-- - 'documents_qwen3_embedding' becomes 'data_documents_qwen3_embedding'
-- - 'documents_zhipu' becomes 'data_documents_zhipu'

-- Qwen3 embedding vector store table (1024 dimensions)
-- This table is auto-created by LlamaIndex during index building
-- Uncomment if you want to pre-create it manually:
/*
CREATE TABLE IF NOT EXISTS data_documents_qwen3_embedding (
    id BIGSERIAL PRIMARY KEY,
    text VARCHAR NOT NULL,
    metadata_ JSON,
    node_id VARCHAR,
    embedding vector(1024)
);
CREATE INDEX IF NOT EXISTS documents_qwen3_embedding_idx_1
    ON data_documents_qwen3_embedding ((metadata_->>'ref_doc_id'));
*/

-- ZhipuAI vector store table (1024 dimensions)
-- This table is auto-created by LlamaIndex during index building
-- Uncomment if you want to pre-create it manually:
/*
CREATE TABLE IF NOT EXISTS data_documents_zhipu (
    id BIGSERIAL PRIMARY KEY,
    text VARCHAR NOT NULL,
    metadata_ JSON,
    node_id VARCHAR,
    embedding vector(1024)
);
CREATE INDEX IF NOT EXISTS documents_zhipu_idx_1
    ON data_documents_zhipu ((metadata_->>'ref_doc_id'));
*/

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Newbee Notebook database initialized successfully';
    RAISE NOTICE 'Extensions enabled: vector, uuid-ossp, pgcrypto';
    RAISE NOTICE 'Core tables: library, notebooks, documents, notebook_document_refs, sessions, messages, references, app_settings';
    RAISE NOTICE 'Legacy tables: chat_sessions, chat_messages';
    RAISE NOTICE 'Document model: library-first (library_id NOT NULL, notebook association via notebook_document_refs)';
    RAISE NOTICE 'Document statuses: uploaded -> pending -> processing -> converted -> completed | failed';
    RAISE NOTICE 'Vector tables: Auto-created by LlamaIndex during index building';
    RAISE NOTICE '  - data_documents_qwen3_embedding (1024 dims)';
    RAISE NOTICE '  - data_documents_zhipu (1024 dims)';
END $$;
