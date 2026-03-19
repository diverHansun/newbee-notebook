CREATE TABLE IF NOT EXISTS diagrams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    diagram_type TEXT NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('reactflow_json', 'mermaid')),
    content_path TEXT NOT NULL,
    document_ids UUID[] NOT NULL DEFAULT '{}',
    node_positions JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diagrams_notebook_id ON diagrams(notebook_id);
CREATE INDEX IF NOT EXISTS idx_diagrams_document_ids ON diagrams USING GIN(document_ids);
