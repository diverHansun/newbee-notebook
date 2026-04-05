from pathlib import Path

from newbee_notebook.infrastructure.document_processing.store import save_markdown


def test_save_markdown_persists_assets_and_rewrites_image_links(tmp_path: Path):
    markdown = "# Title\n\n![img](images/demo.jpg)\n"
    rel_path, content_size = save_markdown(
        document_id="doc-1",
        markdown=markdown,
        image_assets={"images/demo.jpg": b"image-bytes"},
        metadata_assets={"layout.json": b'{"pdf_info": [1, 2, 3]}'},
        base_root=str(tmp_path),
    )

    assert rel_path == "doc-1/markdown/content.md"
    assert content_size > 0

    content_path = tmp_path / rel_path
    saved_markdown = content_path.read_text(encoding="utf-8")
    assert "![img](/api/v1/documents/doc-1/assets/images/demo.jpg)" in saved_markdown

    image_path = tmp_path / "doc-1" / "assets" / "images" / "demo.jpg"
    assert image_path.exists()
    assert image_path.read_bytes() == b"image-bytes"

    meta_path = tmp_path / "doc-1" / "assets" / "meta" / "layout.json"
    assert meta_path.exists()


def test_save_markdown_supports_basename_asset_mapping(tmp_path: Path):
    markdown = "![img](images/ref.jpg)"
    save_markdown(
        document_id="doc-2",
        markdown=markdown,
        image_assets={"ref.jpg": b"img"},
        base_root=str(tmp_path),
    )

    content_path = tmp_path / "doc-2" / "markdown" / "content.md"
    saved_markdown = content_path.read_text(encoding="utf-8")
    assert saved_markdown == "![img](/api/v1/documents/doc-2/assets/images/ref.jpg)"
