"""Markdown-only document loading utilities."""

import os
from pathlib import Path
from typing import List, Optional

from llama_index.core import Document
from llama_index.readers.file import MarkdownReader


def load_documents_from_subdirs(
    base_dir: str,
    subdirs: Optional[List[str]] = None,
    recursive: bool = False,
    exclude_hidden: bool = True,
) -> List[Document]:
    """Load markdown documents from specified subdirectories."""
    target_dir = Path(base_dir)
    if not target_dir.exists():
        raise FileNotFoundError(f"Directory not found: {base_dir}")

    docs: List[Document] = []
    reader = MarkdownReader(remove_hyperlinks=False, remove_images=False)
    subdirs = subdirs or [p.name for p in target_dir.iterdir() if p.is_dir()]
    for subdir in subdirs:
        subdir_path = target_dir / subdir
        if not subdir_path.is_dir():
            continue
        pattern = "**/*.md" if recursive else "*.md"
        for file_path in subdir_path.glob(pattern):
            if exclude_hidden and file_path.name.startswith("."):
                continue
            docs.extend(reader.load_data(str(file_path)))

    if not docs:
        raise ValueError(f"No markdown documents found under {base_dir}")
    return docs


def load_documents(
    input_dir: str,
    recursive: bool = True,
    required_exts: Optional[List[str]] = None,  # kept for compatibility
    exclude_hidden: bool = True,
) -> List[Document]:
    """Load markdown documents from a directory."""
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Directory not found: {input_dir}")

    reader = MarkdownReader(remove_hyperlinks=False, remove_images=False)
    pattern = "**/*.md" if recursive else "*.md"
    documents: List[Document] = []
    for file_path in Path(input_dir).glob(pattern):
        if exclude_hidden and file_path.name.startswith("."):
            continue
        documents.extend(reader.load_data(str(file_path)))

    if not documents:
        raise ValueError(f"No markdown documents found in {input_dir}")

    return documents
