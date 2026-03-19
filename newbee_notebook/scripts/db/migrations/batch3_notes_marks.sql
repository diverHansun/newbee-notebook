CREATE TABLE IF NOT EXISTS marks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    anchor_text TEXT NOT NULL,
    char_offset INTEGER NOT NULL CHECK (char_offset >= 0),
    context_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_marks_document_id ON marks(document_id);
CREATE INDEX IF NOT EXISTS idx_marks_created_at ON marks(created_at);

CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notes_notebook_id ON notes(notebook_id);
CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at);

CREATE TABLE IF NOT EXISTS note_document_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(note_id, document_id)
);
CREATE INDEX IF NOT EXISTS idx_note_document_tags_note_id ON note_document_tags(note_id);
CREATE INDEX IF NOT EXISTS idx_note_document_tags_document_id ON note_document_tags(document_id);

CREATE TABLE IF NOT EXISTS note_mark_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    mark_id UUID NOT NULL REFERENCES marks(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(note_id, mark_id)
);
CREATE INDEX IF NOT EXISTS idx_note_mark_refs_note_id ON note_mark_refs(note_id);
CREATE INDEX IF NOT EXISTS idx_note_mark_refs_mark_id ON note_mark_refs(mark_id);
