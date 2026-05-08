-- Batch 8: user-uploaded chat image metadata

ALTER TABLE IF EXISTS messages
    ADD COLUMN IF NOT EXISTS image_ids JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS chat_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL UNIQUE,
    mime_type VARCHAR(64) NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    width INTEGER,
    height INTEGER,
    sha256 VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_images_session_id
    ON chat_images(session_id);

CREATE INDEX IF NOT EXISTS idx_chat_images_created_at
    ON chat_images(created_at);

CREATE INDEX IF NOT EXISTS idx_chat_images_deleted_at
    ON chat_images(deleted_at);
