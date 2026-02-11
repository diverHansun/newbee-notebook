"""
Newbee Notebook - Library Service

Application service for Library operations.
"""

from typing import Optional, Tuple, List
import logging

from newbee_notebook.domain.entities.library import Library
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.repositories.library_repository import LibraryRepository
from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.domain.repositories.reference_repository import NotebookDocumentRefRepository
from newbee_notebook.domain.value_objects.document_status import DocumentStatus


logger = logging.getLogger(__name__)


class LibraryService:
    """
    Application service for Library management.
    
    Responsibilities:
    - Get or create the Library
    - List and manage Library documents
    - Handle document deletion with reference checking
    """
    
    def __init__(
        self,
        library_repo: LibraryRepository,
        document_repo: DocumentRepository,
        ref_repo: NotebookDocumentRefRepository,
    ):
        self.library_repo = library_repo
        self.document_repo = document_repo
        self.ref_repo = ref_repo
    
    async def get_or_create(self) -> Library:
        """
        Get the Library, creating it if it doesn't exist.
        
        Returns:
            Library instance.
        """
        library = await self.library_repo.get_or_create()
        logger.info(f"Library retrieved: {library.library_id}")
        return library
    
    async def list_documents(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[DocumentStatus] = None,
    ) -> Tuple[List[Document], int]:
        """
        List documents in the Library.
        
        Args:
            limit: Maximum number of documents.
            offset: Number of documents to skip.
            status: Optional status filter.
            
        Returns:
            Tuple of (documents, total_count).
        """
        documents = await self.document_repo.list_by_library(
            limit=limit,
            offset=offset,
            status=status,
        )
        total = await self.document_repo.count_by_library(status=status)
        
        return documents, total
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            document_id: Document unique identifier.
            
        Returns:
            Document if found and belongs to Library.
        """
        document = await self.document_repo.get(document_id)
        if document and document.is_library_document:
            return document
        return None
    
    async def check_document_references(
        self, 
        document_id: str
    ) -> Tuple[int, List[str]]:
        """
        Check if a Library document is referenced by any Notebooks.
        
        Args:
            document_id: Document unique identifier.
            
        Returns:
            Tuple of (reference_count, notebook_ids).
        """
        refs = await self.ref_repo.list_by_document(document_id)
        notebook_ids = [ref.notebook_id for ref in refs]
        return len(refs), notebook_ids
    
    async def delete_document(
        self, 
        document_id: str, 
        force: bool = False
    ) -> bool:
        """
        Delete a Library document.
        
        Args:
            document_id: Document unique identifier.
            force: If True, delete even if referenced.
            
        Returns:
            True if deleted.
            
        Raises:
            ValueError: If document not found.
            RuntimeError: If document is referenced and force=False.
        """
        document = await self.document_repo.get(document_id)
        if not document or not document.is_library_document:
            raise ValueError(f"Library document not found: {document_id}")
        
        # Check references
        ref_count, notebook_ids = await self.check_document_references(document_id)
        if ref_count > 0 and not force:
            raise RuntimeError(
                f"Document is referenced by {ref_count} notebook(s). "
                f"Use force=True to delete anyway."
            )
        
        # Delete references first
        if ref_count > 0:
            await self.ref_repo.delete_by_document(document_id)
            logger.info(f"Deleted {ref_count} references for document {document_id}")
        
        # Delete document
        result = await self.document_repo.delete(document_id)
        
        if result:
            # Update library document count
            await self.library_repo.increment_document_count(-1)
            logger.info(f"Deleted library document: {document_id}")
        
        return result


