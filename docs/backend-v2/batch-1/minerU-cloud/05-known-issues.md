# Known Issues

## 1. `Unclosed client session` appears after successful full pipeline runs

### Current status

Observed in `celery-worker` logs after a document finishes `process_document_task` successfully:

```text
Unclosed client session
Unclosed connector
```

This was reproduced during a successful end-to-end run on `2026-03-09`:
- MinerU local conversion completed
- pgvector / Elasticsearch indexing completed
- document status reached `completed`

So this is currently a resource cleanup issue, not a functional blocker for batch-1 acceptance.

### Scope

The warning appears after the indexing phase, not during MinIO read/write or MinerU conversion request retries.

Current evidence points to an async client lifecycle issue in downstream indexing/storage integrations rather than the MinerU local retry wrapper itself.

### Why not fixed in this batch

Batch-1 priority was:
1. make runtime storage MinIO-only
2. make failed documents re-queue correctly
3. stabilize MinerU local conversion with batch size + retry controls

The `Unclosed client session` warning does not block those goals and should be handled as a follow-up cleanup task with focused tracing.

### Follow-up plan

Recommended next debugging steps:

1. Trace all `aiohttp.ClientSession` creation sites in the document processing and indexing path
2. Confirm ownership and close semantics for shared clients vs per-task clients
3. Add a focused regression test or log assertion once the leaking component is isolated
