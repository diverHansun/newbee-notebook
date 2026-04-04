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
            "epub": cls.EPUB,
            "md": cls.MD,
            "markdown": cls.MD,
            "csv": cls.CSV,
            "xlsx": cls.XLSX,
            "xls": cls.XLSX,
        }
        return mapping.get(ext, cls.TXT)
    
    @classmethod
    def supported_extensions(cls) -> list:
        """Get list of supported file extensions."""
        return ["pdf", "txt", "docx", "doc", "pptx", "epub", "md", "csv", "xlsx", "xls"]


