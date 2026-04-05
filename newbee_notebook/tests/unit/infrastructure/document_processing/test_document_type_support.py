from newbee_notebook.domain.value_objects.document_type import DocumentType
from newbee_notebook.infrastructure.storage.local_storage import SUPPORTED_EXTENSIONS


def test_document_type_recognizes_pptx_and_epub_extensions():
    assert DocumentType.from_extension("pptx") == DocumentType.PPTX
    assert DocumentType.from_extension(".epub") == DocumentType.EPUB


def test_supported_extensions_include_pptx_and_epub():
    extensions = DocumentType.supported_extensions()

    assert "pptx" in extensions
    assert "epub" in extensions
    assert "pptx" in SUPPORTED_EXTENSIONS
    assert "epub" in SUPPORTED_EXTENSIONS
