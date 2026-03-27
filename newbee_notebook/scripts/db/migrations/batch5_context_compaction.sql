ALTER TABLE IF EXISTS sessions
ADD COLUMN IF NOT EXISTS compaction_boundary_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_sessions_compaction_boundary_id
ON sessions(compaction_boundary_id);

ALTER TABLE IF EXISTS messages
ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) NOT NULL DEFAULT 'normal';

ALTER TABLE IF EXISTS messages
DROP CONSTRAINT IF EXISTS messages_message_type_check;

ALTER TABLE IF EXISTS messages
ADD CONSTRAINT messages_message_type_check
CHECK (message_type IN ('normal', 'summary'));
