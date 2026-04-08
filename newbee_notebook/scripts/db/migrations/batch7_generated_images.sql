-- Batch 7: generated image metadata persistence

CREATE TABLE IF NOT EXISTS generated_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    tool_call_id VARCHAR(128) NOT NULL DEFAULT '',
    prompt TEXT NOT NULL,
    provider VARCHAR(32) NOT NULL,
    model VARCHAR(128) NOT NULL,
    size VARCHAR(32),
    width INTEGER,
    height INTEGER,
    storage_key TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_images_session_id
    ON generated_images(session_id);

CREATE INDEX IF NOT EXISTS idx_generated_images_notebook_id
    ON generated_images(notebook_id);

CREATE INDEX IF NOT EXISTS idx_generated_images_message_id
    ON generated_images(message_id);

CREATE INDEX IF NOT EXISTS idx_generated_images_created_at
    ON generated_images(created_at);
