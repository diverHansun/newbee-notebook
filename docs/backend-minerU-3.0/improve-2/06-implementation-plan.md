# MinerU Improve-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the default MinerU cloud path to support `pdf/doc/docx/ppt/pptx/html/images`, route HTML through `MinerU-HTML`, batch eligible notebook additions into shared cloud batches, keep oversized documents on the fallback path, refresh smoke/docs, and verify the end-to-end upload flow.

**Architecture:** Keep the existing single-document `DocumentProcessor` flow for fallback and local/GPU paths, but add a dedicated cloud batch orchestration layer for notebook-triggered full-pipeline conversions. The batch layer will group eligible documents by route, send one or more `/api/v4/file-urls/batch` requests, persist per-document markdown/assets, then reuse the existing indexing tasks. Unsupported or oversized files continue through the current fallback behavior.

**Tech Stack:** FastAPI, Celery, requests, pypdf, Next.js/React, pytest, vitest, Playwright MCP

---

### Task 1: Expand Upload And Type Support

**Files:**
- Modify: `newbee_notebook/domain/value_objects/document_type.py`
- Modify: `newbee_notebook/infrastructure/storage/local_storage.py`
- Test: `newbee_notebook/tests/unit/infrastructure/document_processing/test_document_type_support.py`
- Test: `frontend/src/app/library/page.test.tsx`

- [ ] **Step 1: Write the failing tests**

```python
def test_document_type_recognizes_html_and_common_images():
    assert DocumentType.from_extension("html").value == "html"
    assert DocumentType.from_extension("htm").value == "html"
    assert DocumentType.from_extension("png").value == "image"
    assert DocumentType.from_extension("jpeg").value == "image"
    assert "html" in DocumentType.supported_extensions()
    assert "png" in SUPPORTED_EXTENSIONS
    assert "jpg" in SUPPORTED_EXTENSIONS
    assert "ppt" in SUPPORTED_EXTENSIONS
```

```tsx
it("exposes html, ppt, and common image formats in the upload input", async () => {
  const { container } = renderLibraryPage();
  const input = container.querySelector('input[type="file"]');
  expect(input?.getAttribute("accept")).toContain(".html");
  expect(input?.getAttribute("accept")).toContain(".ppt");
  expect(input?.getAttribute("accept")).toContain(".png");
  expect(input?.getAttribute("accept")).toContain(".jpg");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/document_processing/test_document_type_support.py -v`

Run: `pnpm --dir frontend test -- --run frontend/src/app/library/page.test.tsx`

Expected: new extension assertions fail because `html`, `ppt`, and image formats are not yet recognized.

- [ ] **Step 3: Write minimal implementation**

```python
class DocumentType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    PPTX = "pptx"
    EPUB = "epub"
    MD = "md"
    CSV = "csv"
    XLSX = "xlsx"
    HTML = "html"
    IMAGE = "image"

    @classmethod
    def from_extension(cls, ext: str) -> "DocumentType":
        mapping = {
            "pdf": cls.PDF,
            "txt": cls.TXT,
            "docx": cls.DOCX,
            "doc": cls.DOCX,
            "pptx": cls.PPTX,
            "ppt": cls.PPTX,
            "epub": cls.EPUB,
            "md": cls.MD,
            "markdown": cls.MD,
            "csv": cls.CSV,
            "xlsx": cls.XLSX,
            "xls": cls.XLSX,
            "html": cls.HTML,
            "htm": cls.HTML,
            "png": cls.IMAGE,
            "jpg": cls.IMAGE,
            "jpeg": cls.IMAGE,
            "bmp": cls.IMAGE,
            "webp": cls.IMAGE,
            "tif": cls.IMAGE,
            "tiff": cls.IMAGE,
        }
        return mapping.get(ext, cls.TXT)
```

```python
SUPPORTED_EXTENSIONS = {
    "pdf", "txt", "md", "markdown", "csv", "xls", "xlsx",
    "doc", "docx", "ppt", "pptx", "epub", "html", "htm",
    "png", "jpg", "jpeg", "bmp", "webp", "tif", "tiff",
}
```

```tsx
const DOCUMENT_UPLOAD_ACCEPT =
  ".pdf,.txt,.md,.markdown,.csv,.xls,.xlsx,.doc,.docx,.ppt,.pptx,.epub,.html,.htm,.png,.jpg,.jpeg,.bmp,.webp,.tif,.tiff";
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/document_processing/test_document_type_support.py -v`

Run: `pnpm --dir frontend test -- --run frontend/src/app/library/page.test.tsx`

Expected: PASS

- [ ] **Step 5: Review diff and keep changes uncommitted**

```bash
git diff -- newbee_notebook/domain/value_objects/document_type.py newbee_notebook/infrastructure/storage/local_storage.py newbee_notebook/tests/unit/infrastructure/document_processing/test_document_type_support.py frontend/src/app/library/page.test.tsx
```

### Task 2: Expand Cloud Converter And Fallback Routing

**Files:**
- Modify: `newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py`
- Modify: `newbee_notebook/infrastructure/document_processing/processor.py`
- Test: `newbee_notebook/tests/unit/infrastructure/document_processing/test_document_processing_processor.py`
- Test: `newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_converter.py`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("ext", [".ppt", ".pptx", ".html", ".htm", ".png", ".jpg"])
def test_processor_cloud_mode_prefers_mineru_for_new_types(ext: str):
    processor = DocumentProcessor(config=_base_config())
    converters = processor._get_converters_for_ext(ext)
    assert isinstance(converters[0], MinerUCloudConverter)
```

```python
def test_cloud_converter_routes_html_to_mineru_html(monkeypatch):
    converter = MinerUCloudConverter(api_key="test", model_version="vlm")
    payload = converter._build_request_payload(file_name="demo.html", data_id="doc-1")
    assert payload["model_version"] == "MinerU-HTML"
```

```python
def test_cloud_converter_rejects_oversized_pdf_before_upload(tmp_path):
    path = tmp_path / "oversized.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    converter = MinerUCloudConverter(api_key="test")
    with pytest.raises(MinerUCloudLimitExceededError):
        converter._validate_cloud_limits(path, page_count=201)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/document_processing/test_document_processing_processor.py newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_converter.py -v`

Expected: FAIL because the new route, extensions, and limit guards do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class MinerUCloudLimitExceededError(RuntimeError):
    """Cloud request exceeds official MinerU limits and should fall back."""
```

```python
SUPPORTED_EXTENSIONS = frozenset({
    ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".html", ".htm", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff",
})

def _resolve_model_version_for_file(self, path: Path) -> str | None:
    if path.suffix.lower() in {".html", ".htm"}:
        return "MinerU-HTML"
    if (self._model_version or "").strip() == "MinerU-HTML":
        logger.warning("Ignoring MinerU-HTML model_version for non-HTML file: %s", path.name)
        return None
    return self._model_version
```

```python
def _validate_cloud_limits(self, path: Path, page_count: int | None) -> None:
    size_bytes = path.stat().st_size
    if size_bytes > 200 * 1024 * 1024:
        raise MinerUCloudLimitExceededError(f"MinerU cloud size limit exceeded for {path.name}")
    if path.suffix.lower() == ".pdf" and page_count and page_count > 200:
        raise MinerUCloudLimitExceededError(f"MinerU cloud page limit exceeded for {path.name}")
```

```python
if isinstance(converter, MinerUCloudConverter) and isinstance(e, MinerUCloudLimitExceededError):
    logger.warning("MinerU cloud limit exceeded for %s: %s. Falling back.", file_path, e)
    last_error = e
    continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/infrastructure/document_processing/test_document_processing_processor.py newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_converter.py -v`

Expected: PASS

- [ ] **Step 5: Review diff and keep changes uncommitted**

```bash
git diff -- newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py newbee_notebook/infrastructure/document_processing/processor.py newbee_notebook/tests/unit/infrastructure/document_processing/test_document_processing_processor.py newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_converter.py
```

### Task 3: Add Shared Cloud Batch Orchestration

**Files:**
- Create: `newbee_notebook/infrastructure/document_processing/cloud_batch_service.py`
- Modify: `newbee_notebook/application/services/notebook_document_service.py`
- Modify: `newbee_notebook/infrastructure/tasks/document_tasks.py`
- Test: `newbee_notebook/tests/unit/application/services/test_notebook_document_service_actions.py`
- Test: `newbee_notebook/tests/unit/infrastructure/tasks/test_document_tasks_pipeline_controls.py`
- Test: `newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_batch_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_add_documents_dispatches_cloud_batch_for_full_pipeline_docs(monkeypatch):
    delay = Mock()
    monkeypatch.setattr(
        "newbee_notebook.application.services.notebook_document_service.process_document_cloud_batch_task.delay",
        delay,
    )
    result = asyncio.run(service.add_documents("nb-1", ["doc-1", "doc-2"]))
    delay.assert_called_once_with(["doc-1", "doc-2"])
```

```python
def test_batch_service_groups_html_and_default_routes():
    groups = build_cloud_batches([
        _item("a.pdf"),
        _item("b.docx"),
        _item("c.html"),
    ])
    assert len(groups["default"]) == 2
    assert len(groups["html"]) == 1
```

```python
def test_batch_service_slices_every_50_documents():
    items = [_item(f"doc-{idx}.pdf") for idx in range(52)]
    batches = slice_cloud_batches(items, batch_size=50)
    assert [len(batch) for batch in batches] == [50, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_notebook_document_service_actions.py newbee_notebook/tests/unit/infrastructure/tasks/test_document_tasks_pipeline_controls.py newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_batch_service.py -v`

Expected: FAIL because the batch task/service does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class CloudBatchDocument:
    document_id: str
    title: str
    local_path: Path
    route: str
```

```python
def _enqueue_full_pipeline_documents(self, document_ids: list[str]) -> None:
    if _cloud_batch_enabled():
        process_document_cloud_batch_task.delay(document_ids)
        return
    for document_id in document_ids:
        process_document_task.delay(document_id, force=False)
```

```python
@app.task(name="newbee_notebook.infrastructure.tasks.document_tasks.process_document_cloud_batch_task")
def process_document_cloud_batch_task(document_ids: list[str]) -> None:
    asyncio.run(_process_document_cloud_batch_async(document_ids))
```

```python
for result in batch_results:
    await ctx.doc_repo.update_status(
        document_id=result.document_id,
        status=DocumentStatus.CONVERTED,
        content_path=result.content_path,
        content_format="markdown",
        content_size=result.content_size,
        page_count=result.page_count,
        processing_stage=ProcessingStage.FINALIZING.value,
    )
    index_document_task.delay(result.document_id, force=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/unit/application/services/test_notebook_document_service_actions.py newbee_notebook/tests/unit/infrastructure/tasks/test_document_tasks_pipeline_controls.py newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_batch_service.py -v`

Expected: PASS

- [ ] **Step 5: Review diff and keep changes uncommitted**

```bash
git diff -- newbee_notebook/infrastructure/document_processing/cloud_batch_service.py newbee_notebook/application/services/notebook_document_service.py newbee_notebook/infrastructure/tasks/document_tasks.py newbee_notebook/tests/unit/application/services/test_notebook_document_service_actions.py newbee_notebook/tests/unit/infrastructure/tasks/test_document_tasks_pipeline_controls.py newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_batch_service.py
```

### Task 4: Upgrade Smoke Tool And Docs

**Files:**
- Modify: `scripts/mineru_v4_smoke_test.py`
- Modify: `quickstart.md`
- Modify: `scripts/README.md`
- Delete: `scripts/up-mineru.ps1`
- Test: `newbee_notebook/tests/smoke/test_mineru_v4_smoke_script.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_smoke_script_accepts_multiple_paths_and_routes_html():
    parser = build_parser()
    args = parser.parse_args(["demo.pdf", "demo.html"])
    assert args.paths == ["demo.pdf", "demo.html"]
```

```python
def test_scripts_readme_no_longer_mentions_up_mineru():
    text = Path("scripts/README.md").read_text(encoding="utf-8")
    assert "up-mineru.ps1" not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/smoke/test_mineru_v4_smoke_script.py -v`

Expected: FAIL because the smoke test module and docs cleanup are not done.

- [ ] **Step 3: Write minimal implementation**

```python
parser.add_argument("paths", nargs="+", help="One or more local file paths to test.")
```

```python
def _resolve_model_version(path: Path, explicit_model_version: str) -> str | None:
    if path.suffix.lower() in {".html", ".htm"}:
        return "MinerU-HTML"
    return explicit_model_version or None
```

```md
- 默认 `docker compose up -d` 使用 MinerU v4 cloud API
- 支持 `pdf/doc/docx/ppt/pptx/html/图片`
- `html` 自动走 `MinerU-HTML`
- 超过 `200 MB` 或 `200 页` 的文档会走 fallback
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest newbee_notebook/tests/smoke/test_mineru_v4_smoke_script.py newbee_notebook/tests/smoke/test_docker_compose_stack.py -v`

Expected: PASS

- [ ] **Step 5: Review diff and keep changes uncommitted**

```bash
git diff -- scripts/mineru_v4_smoke_test.py quickstart.md scripts/README.md newbee_notebook/tests/smoke/test_mineru_v4_smoke_script.py scripts/up-mineru.ps1
```

### Task 5: End-To-End And Regression Verification

**Files:**
- Verify only: existing backend/frontend app runtime
- Verify only: `C:\Users\Huang junzhe\Downloads\实验1.2-hadoop系统的安装和使用.ppt`
- Verify only: one downloaded `.html` sample

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest `
  newbee_notebook/tests/unit/infrastructure/document_processing/test_document_type_support.py `
  newbee_notebook/tests/unit/infrastructure/document_processing/test_document_processing_processor.py `
  newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_converter.py `
  newbee_notebook/tests/unit/infrastructure/document_processing/test_mineru_cloud_batch_service.py `
  newbee_notebook/tests/unit/application/services/test_notebook_document_service_actions.py `
  newbee_notebook/tests/unit/infrastructure/tasks/test_document_tasks_pipeline_controls.py `
  newbee_notebook/tests/smoke/test_mineru_v4_smoke_script.py `
  newbee_notebook/tests/smoke/test_docker_compose_stack.py -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
pnpm --dir frontend test -- --run frontend/src/app/library/page.test.tsx frontend/src/components/sources/source-list.test.tsx
```

Expected: PASS

- [ ] **Step 3: Start app stack for e2e**

Run:

```bash
docker compose up -d
```

Expected: `frontend` on `http://localhost:3000`, API on `http://localhost:8000`.

- [ ] **Step 4: Use Playwright MCP to verify the user flow**

Test flow:

1. Open `http://localhost:3000/`
2. Upload `C:\Users\Huang junzhe\Downloads\实验1.2-hadoop系统的安装和使用.ppt` on the Library page
3. Download or create one HTML sample and upload it too
4. Open a notebook, add both documents from Sources
5. Wait for conversion to finish
6. Confirm both documents appear in Sources and at least one converted markdown view opens successfully

- [ ] **Step 5: Stop and report without committing**

Run:

```bash
git status --short --branch
```

Expected: modified files remain uncommitted for user review.
