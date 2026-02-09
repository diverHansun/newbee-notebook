# Documents Storage

This directory stores uploaded and processed documents in the runtime pipeline.

## Current Layout

Each document is stored under its `document_id`:

```text
data/documents/{document_id}/
  original/               # Uploaded source file
  markdown/content.md     # Converted markdown used by retrieval
  assets/images/          # Image assets referenced by markdown
  assets/meta/            # Optional metadata files (layout/content list/json)
```

## Notes

- Do not pre-create type-based folders like `pdf/`, `txt/`, `word/`, etc.
- Files and folders are created automatically by upload + processing tasks.
- Safe to clean generated document folders when resetting local test data.
