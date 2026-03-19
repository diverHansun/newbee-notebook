"""
Newbee Notebook - Domain Entities Package
"""

from newbee_notebook.domain.entities.base import Entity
from newbee_notebook.domain.entities.library import Library
from newbee_notebook.domain.entities.notebook import Notebook
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.entities.reference import Reference, NotebookDocumentRef
from newbee_notebook.domain.entities.diagram import Diagram

__all__ = [
    "Entity",
    "Library",
    "Notebook",
    "Document",
    "Session",
    "Reference",
    "NotebookDocumentRef",
    "Diagram",
]


