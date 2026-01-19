"""Document loading utilities using LlamaIndex SimpleDirectoryReader.

This module wraps LlamaIndex's document loading functionality to provide
a consistent interface for loading documents from various file formats.
Documents are organized by type in subdirectories: txt/, pdf/, csv/, md/, excel/, word/
"""

import os
from typing import List, Optional
from pathlib import Path
from llama_index.core import SimpleDirectoryReader, Document
from llama_index.readers.file import PandasExcelReader
from llama_index.readers.file.docs import DocxReader


def load_documents_from_subdirs(
    base_dir: str,
    subdirs: Optional[List[str]] = None,
    recursive: bool = False,
    exclude_hidden: bool = True,
) -> List[Document]:
    """Load documents from specified subdirectories organized by file type.
    
    This function loads documents from subdirectories like txt/, pdf/, csv/, md/, excel/
    under the base directory, rather than loading all files recursively.
    
    Args:
        base_dir: Base directory path (e.g., "data/documents")
        subdirs: List of subdirectory names to load from. If None, loads from all type subdirs:
                 ["txt", "pdf", "csv", "md", "excel"]
        recursive: Whether to recursively read within each subdirectory
        exclude_hidden: Whether to exclude hidden files (starting with .)
    
    Returns:
        List[Document]: List of loaded Document objects with metadata from all subdirectories
    
    Raises:
        FileNotFoundError: If base_dir does not exist
        ValueError: If no documents found in any subdirectory
    
    Example:
        >>> # Load from all type subdirectories
        >>> documents = load_documents_from_subdirs("data/documents")
        >>> print(f"Loaded {len(documents)} documents")
        
        >>> # Load only from specific subdirectories
        >>> documents = load_documents_from_subdirs("data/documents", subdirs=["txt", "pdf"])
    """
    if not os.path.exists(base_dir):
        raise FileNotFoundError(f"Directory not found: {base_dir}")
    
    # Default subdirectories to load from
    if subdirs is None:
        subdirs = ["txt", "pdf", "csv", "md", "excel", "word"]

    # Configure file extractor for Excel and Word files
    file_extractor = {
        ".xlsx": PandasExcelReader(),
        ".xls": PandasExcelReader(),
        ".docx": DocxReader(),
    }
    
    # Mapping of subdirectory to file extensions
    subdir_to_exts = {
        "txt": [".txt"],
        "pdf": [".pdf"],
        "csv": [".csv"],
        "md": [".md"],
        "excel": [".xlsx", ".xls"],
        "word": [".docx"],
    }
    
    all_documents = []
    loaded_subdirs = []
    
    # Load documents from each specified subdirectory
    for subdir in subdirs:
        subdir_path = os.path.join(base_dir, subdir)
        
        # Skip if subdirectory doesn't exist
        if not os.path.exists(subdir_path):
            continue
        
        # Check if subdirectory is empty (only contains .gitkeep)
        files = [f for f in os.listdir(subdir_path) if not f.startswith('.')]
        if not files:
            continue
        
        # Get required extensions for this subdirectory
        required_exts = subdir_to_exts.get(subdir, None)
        if required_exts is None:
            continue
        
        try:
            reader = SimpleDirectoryReader(
                input_dir=subdir_path,
                recursive=recursive,
                required_exts=required_exts,
                exclude_hidden=exclude_hidden,
                file_extractor=file_extractor,
            )
            
            docs = reader.load_data()
            if docs:
                all_documents.extend(docs)
                loaded_subdirs.append(subdir)
                print(f"  - Loaded {len(docs)} documents from {subdir}/ directory")
        except Exception as e:
            print(f"  - Warning: Failed to load from {subdir}/ directory: {e}")
            continue
    
    if not all_documents:
        raise ValueError(
            f"No documents found in subdirectories {subdirs} under {base_dir}. "
            f"Please add documents to the respective subdirectories (txt/, pdf/, csv/, md/, excel/, word/)."
        )
    
    print(f"  - Total: {len(all_documents)} documents from {len(loaded_subdirs)} subdirectories")
    return all_documents


def load_documents(
    input_dir: str,
    recursive: bool = True,
    required_exts: Optional[List[str]] = None,
    exclude_hidden: bool = True,
) -> List[Document]:
    """Load documents from a single directory using SimpleDirectoryReader.
    
    Note: For loading from organized subdirectories (txt/, pdf/, csv/, etc.),
    use load_documents_from_subdirs() instead.
    
    Args:
        input_dir: Path to the directory containing documents
        recursive: Whether to recursively read subdirectories
        required_exts: List of required file extensions (e.g., [".txt", ".pdf"])
                      If None, loads all supported formats
        exclude_hidden: Whether to exclude hidden files (starting with .)
    
    Returns:
        List[Document]: List of loaded Document objects with metadata
    
    Raises:
        FileNotFoundError: If input_dir does not exist
        ValueError: If no documents found in the directory
    
    Example:
        >>> documents = load_documents("data/documents/txt", required_exts=[".txt"])
        >>> print(f"Loaded {len(documents)} documents")
    """
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Directory not found: {input_dir}")
    
    # Set default extensions if not specified
    if required_exts is None:
        required_exts = [".txt", ".pdf", ".csv", ".md", ".xlsx", ".xls", ".docx"]

    # Configure file extractor for Excel and Word files
    file_extractor = {
        ".xlsx": PandasExcelReader(),
        ".xls": PandasExcelReader(),
        ".docx": DocxReader(),
    }
    
    # Load documents using SimpleDirectoryReader
    reader = SimpleDirectoryReader(
        input_dir=input_dir,
        recursive=recursive,
        required_exts=required_exts,
        exclude_hidden=exclude_hidden,
        file_extractor=file_extractor,
    )
    
    documents = reader.load_data()
    
    if not documents:
        raise ValueError(f"No documents found in {input_dir} with extensions {required_exts}")
    
    return documents


def load_txt_files(input_dir: str, recursive: bool = True) -> List[Document]:
    """Load only TXT files from a directory.
    
    Args:
        input_dir: Path to the directory containing TXT files
        recursive: Whether to recursively read subdirectories
    
    Returns:
        List[Document]: List of loaded TXT documents
    
    Example:
        >>> txt_docs = load_txt_files("data/documents/txt")
    """
    return load_documents(input_dir, recursive=recursive, required_exts=[".txt"])


def load_pdf_files(input_dir: str, recursive: bool = True) -> List[Document]:
    """Load only PDF files from a directory.
    
    Args:
        input_dir: Path to the directory containing PDF files
        recursive: Whether to recursively read subdirectories
    
    Returns:
        List[Document]: List of loaded PDF documents
    
    Example:
        >>> pdf_docs = load_pdf_files("data/documents/pdf")
    """
    return load_documents(input_dir, recursive=recursive, required_exts=[".pdf"])


def load_csv_files(input_dir: str, recursive: bool = True) -> List[Document]:
    """Load only CSV files from a directory.
    
    Args:
        input_dir: Path to the directory containing CSV files
        recursive: Whether to recursively read subdirectories
    
    Returns:
        List[Document]: List of loaded CSV documents
    
    Example:
        >>> csv_docs = load_csv_files("data/documents/csv")
    """
    return load_documents(input_dir, recursive=recursive, required_exts=[".csv"])


def load_md_files(input_dir: str, recursive: bool = True) -> List[Document]:
    """Load only Markdown files from a directory.
    
    Args:
        input_dir: Path to the directory containing Markdown files
        recursive: Whether to recursively read subdirectories
    
    Returns:
        List[Document]: List of loaded Markdown documents
    
    Example:
        >>> md_docs = load_md_files("data/documents/md")
    """
    return load_documents(input_dir, recursive=recursive, required_exts=[".md"])


def load_excel_files(input_dir: str, recursive: bool = True) -> List[Document]:
    """Load only Excel files from a directory.

    Supports both .xlsx and .xls formats. Each sheet in the Excel file
    will be loaded as a separate document.

    Args:
        input_dir: Path to the directory containing Excel files
        recursive: Whether to recursively read subdirectories

    Returns:
        List[Document]: List of loaded Excel documents

    Example:
        >>> excel_docs = load_excel_files("data/documents/excel")
    """
    return load_documents(input_dir, recursive=recursive, required_exts=[".xlsx", ".xls"])


def load_word_files(input_dir: str, recursive: bool = True) -> List[Document]:
    """Load only Word files from a directory.

    Supports .docx format.

    Args:
        input_dir: Path to the directory containing Word files
        recursive: Whether to recursively read subdirectories

    Returns:
        List[Document]: List of loaded Word documents

    Example:
        >>> word_docs = load_word_files("data/documents/word")
    """
    return load_documents(input_dir, recursive=recursive, required_exts=[".docx"])



