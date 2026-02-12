# Streaming & Context Protocol (API v1)

- SSE events for `/api/v1/chat/notebooks/{id}/chat/stream`:
  - `start` {message_id}
  - `content` {delta}
  - `sources` {sources: []}  (sent once after full content)
  - `done` {}
  - `error` {error_code, message}
  - Heartbeat every 15s unchanged
- Message persistence: only after `done` without error/timeout/cancel.
- Timeout: 60s -> `error` (timeout), not persisted.
- Context payload (optional):
  - `selected_text`, `chunk_id`, `document_id`, `page_number`
  - Used to bias answer; selected_text stored to references when provided.
- Scope: RAG restricted to current Notebook documents.
