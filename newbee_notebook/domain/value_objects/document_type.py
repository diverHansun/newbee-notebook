"""
Newbee Notebook - Document Type Value Object
"""

from enum import Enum


class DocumentType(str, Enum):
    """Supported document types."""
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
        """Get document type from file extension."""
        ext = ext.lower().lstrip(".")
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
            "gif": cls.IMAGE,
            "jp2": cls.IMAGE,
            "tif": cls.IMAGE,
            "tiff": cls.IMAGE,
        }
        return mapping.get(ext, cls.TXT)
    
    @classmethod
    def supported_extensions(cls) -> list:
        """Get list of supported file extensions."""
        return [
            "pdf",
            "txt",
            "docx",
            "doc",
            "ppt",
            "pptx",
            "epub",
            "md",
            "csv",
            "xlsx",
            "xls",
            "html",
            "htm",
            "png",
            "jpg",
            "jpeg",
            "bmp",
            "webp",
            "gif",
            "jp2",
            "tif",
            "tiff",
        ]


