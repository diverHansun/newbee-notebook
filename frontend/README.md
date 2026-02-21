# Newbee Notebook Frontend (P1)

## Quick Start

```bash
cd frontend
pnpm install
pnpm dev
```

## P1 Scope Implemented

- Next.js App Router scaffold under `frontend/`
- API contract modules for notebooks/library/documents/sessions/chat
- SSE stream parser and stream hook (`AbortController` + cancel endpoint best-effort)
- Notebook workspace skeleton: Sources / Main / Studio
- Chat and Ask stream loop
- Explain / Conclude interaction chain with a simplified floating card
- Source compatibility layer (`text ?? content`)

## P1 Decisions Aligned

- `converted` status is treated as readable in frontend (View enabled)
- RAG blocking hint shown for `uploaded|pending|processing|converted`
- Cancel strategy: client abort first, server cancel endpoint as best-effort
- Package manager fixed to `pnpm`
