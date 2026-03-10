# Known Issues

## 1. Historical: `Unclosed client session` after successful full pipeline runs

### Root cause

This warning was reproduced on `2026-03-09` and traced to the worker indexing path:

- `document_tasks.py` loaded temporary pgvector / Elasticsearch indexes per task
- the underlying vector store clients were not closed after insert/delete operations
- Elasticsearch's async client surfaced the leak as:

```text
Unclosed client session
Unclosed connector
```

### Resolution

Fixed on `2026-03-10` by adding explicit best-effort close handling for loaded vector-store indexes in the Celery document task pipeline:

1. close nested async vector-store clients when present
2. close direct async vector stores otherwise
3. run cleanup after both indexing and delete-node flows

### Verification

Verified with:

1. focused unit tests covering ES/pgvector index cleanup
2. worker regression tests for document task flows
3. real end-to-end reprocessing of `test.pdf`

In the post-fix worker log window, the document finished successfully and the previous `Unclosed connector` warning did not reappear.
