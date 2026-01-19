"""Document loader module for loading various file formats.

This module provides utilities to load medical documents from different file formats
using LlamaIndex's SimpleDirectoryReader. Supports TXT, PDF, CSV, MD, XLSX, and XLS files.
"""

from medimind_agent.core.rag.document_loader.loader import (
    load_documents,
    load_documents_from_subdirs,
    load_txt_files,
    load_pdf_files,
    load_csv_files,
    load_md_files,
    load_excel_files,
)

__all__ = [
    "load_documents",
    "load_documents_from_subdirs",
    "load_txt_files",
    "load_pdf_files",
    "load_csv_files",
    "load_md_files",
    "load_excel_files",
]



