from newbee_notebook.domain.value_objects.document_type import DocumentType
from newbee_notebook.infrastructure.storage.local_storage import SUPPORTED_EXTENSIONS


def test_document_type_recognizes_pptx_and_epub_extensions():
    assert DocumentType.from_extension("pptx") == DocumentType.PPTX
    assert DocumentType.from_extension(".epub") == DocumentType.EPUB


def test_document_type_recognizes_html_and_common_image_extensions():
    assert DocumentType.from_extension("html") == DocumentType.HTML
    assert DocumentType.from_extension(".htm") == DocumentType.HTML
    assert DocumentType.from_extension("png") == DocumentType.IMAGE
    assert DocumentType.from_extension(".jpeg") == DocumentType.IMAGE
    assert DocumentType.from_extension("jpg") == DocumentType.IMAGE
    assert DocumentType.from_extension("gif") == DocumentType.IMAGE
    assert DocumentType.from_extension(".jp2") == DocumentType.IMAGE


def test_supported_extensions_include_pptx_and_epub():
    extensions = DocumentType.supported_extensions()

    assert "pptx" in extensions
    assert "epub" in extensions
    assert "pptx" in SUPPORTED_EXTENSIONS
    assert "epub" in SUPPORTED_EXTENSIONS


def test_supported_extensions_include_html_ppt_and_images():
    extensions = DocumentType.supported_extensions()

    assert "ppt" in extensions
    assert "html" in extensions
    assert "htm" in extensions
    assert "png" in extensions
    assert "jpg" in extensions
    assert "jpeg" in extensions
    assert "gif" in extensions
    assert "jp2" in extensions
    assert "ppt" in SUPPORTED_EXTENSIONS
    assert "html" in SUPPORTED_EXTENSIONS
    assert "htm" in SUPPORTED_EXTENSIONS
    assert "png" in SUPPORTED_EXTENSIONS
    assert "jpg" in SUPPORTED_EXTENSIONS
    assert "jpeg" in SUPPORTED_EXTENSIONS
    assert "gif" in SUPPORTED_EXTENSIONS
    assert "jp2" in SUPPORTED_EXTENSIONS
