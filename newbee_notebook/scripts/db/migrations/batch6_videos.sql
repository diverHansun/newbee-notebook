CREATE TABLE IF NOT EXISTS video_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID REFERENCES notebooks(id) ON DELETE SET NULL,
    platform TEXT NOT NULL,
    video_id TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    cover_url TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    uploader_name TEXT NOT NULL DEFAULT '',
    uploader_id TEXT NOT NULL DEFAULT '',
    stats JSONB,
    transcript_source TEXT NOT NULL DEFAULT '',
    transcript_path TEXT,
    summary_content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed')),
    error_message TEXT,
    document_ids UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform, video_id)
);

CREATE INDEX IF NOT EXISTS idx_video_summaries_notebook_id ON video_summaries(notebook_id);
CREATE INDEX IF NOT EXISTS idx_video_summaries_status ON video_summaries(status);
CREATE INDEX IF NOT EXISTS idx_video_summaries_document_ids ON video_summaries USING GIN(document_ids);
