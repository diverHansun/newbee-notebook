-- PostgreSQL initialization script for MediMind Agent
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

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

-- ============================================================================
-- Multi-Provider Vector Store Tables
-- ============================================================================
-- Note: These tables are created by LlamaIndex automatically when building indexes.
-- The definitions below are for reference only and match the expected schema.
--
-- LlamaIndex automatically prefixes table names with 'data_', so:
-- - 'documents_biobert' becomes 'data_documents_biobert'
-- - 'documents_zhipu' becomes 'data_documents_zhipu'

-- BioBERT vector store table (768 dimensions)
-- This table is auto-created by LlamaIndex during index building
-- Uncomment if you want to pre-create it manually:
/*
CREATE TABLE IF NOT EXISTS data_documents_biobert (
    id BIGSERIAL PRIMARY KEY,
    text VARCHAR NOT NULL,
    metadata_ JSON,
    node_id VARCHAR,
    embedding vector(768)
);
CREATE INDEX IF NOT EXISTS documents_biobert_idx_1
    ON data_documents_biobert ((metadata_->>'ref_doc_id'));
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
    RAISE NOTICE 'MediMind database initialized successfully';
    RAISE NOTICE 'Extensions enabled: vector, uuid-ossp';
    RAISE NOTICE 'Tables created: chat_sessions, chat_messages';
    RAISE NOTICE 'Vector tables: Auto-created by LlamaIndex during index building';
    RAISE NOTICE '  - data_documents_biobert (768 dims)';
    RAISE NOTICE '  - data_documents_zhipu (1024 dims)';
END $$;
