"""
MediMind Agent - Document Repository Interface
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from medimind_agent.domain.entities.document import Document
from medimind_agent.domain.value_objects.document_status import DocumentStatus


class DocumentRepository(ABC):
    """Repository interface for Document operations."""
    
    @abstractmethod
    async def get(self, document_id: str) -> Optional[Document]:
        """
        Get a Document by ID.
        
        Args:
            document_id: Document unique identifier.
            
        Returns:
            Document instance or None if not found.
        """
        pass
    
    @abstractmethod
    async def get_batch(self, document_ids: List[str]) -> List[Document]:
        """
        Get multiple Documents by IDs.
        
        Args:
            document_ids: List of document IDs.
            
        Returns:
            List of Document instances (order not guaranteed).
        """
        pass
    
    @abstractmethod
    async def list_by_library(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[DocumentStatus] = None
    ) -> List[Document]:
        """
        List Documents in Library.
        
        Args:
            limit: Maximum number of results.
            offset: Number of results to skip.
            status: Optional status filter.
            
        Returns:
            List of Document instances.
        """
        pass
    
    @abstractmethod
    async def list_by_notebook(
        self,
        notebook_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Document]:
        """
        List Documents owned by a Notebook (not including references).
        
        Args:
            notebook_id: Notebook unique identifier.
            limit: Maximum number of results.
            offset: Number of results to skip.
            
        Returns:
            List of Document instances.
        """
        pass
    
    @abstractmethod
    async def count_by_library(self, status: Optional[DocumentStatus] = None) -> int:
        """
        Count Documents in Library.
        
        Args:
            status: Optional status filter.
            
        Returns:
            Total count.
        """
        pass
    
    @abstractmethod
    async def count_by_notebook(self, notebook_id: str) -> int:
        """
        Count Documents owned by a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Total count.
        """
        pass
    
    @abstractmethod
    async def create(self, document: Document) -> Document:
        """
        Create a Document.
        
        Args:
            document: Document instance to create.
            
        Returns:
            Created Document instance.
        """
        pass
    
    @abstractmethod
    async def update(self, document: Document) -> Document:
        """
        Update a Document.
        
        Args:
            document: Document instance with updated values.
            
        Returns:
            Updated Document instance.
        """
        pass
    
    @abstractmethod
    async def delete(self, document_id: str) -> bool:
        """
        Delete a Document.
        
        Args:
            document_id: Document unique identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    async def update_status(
        self, 
        document_id: str, 
        status: DocumentStatus,
        chunk_count: Optional[int] = None,
        page_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update Document processing status.
        
        Args:
            document_id: Document unique identifier.
            status: New status.
            chunk_count: Optional chunk count update.
            page_count: Optional page count update.
            error_message: Optional error message when failed.
        """
        pass
    
    @abstractmethod
    async def delete_by_notebook(self, notebook_id: str) -> int:
        """
        Delete all Documents owned by a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Number of documents deleted.
        """
        pass

    @abstractmethod
    async def count_all(self, status: Optional[DocumentStatus] = None) -> int:
        """
        Count all Documents with optional status filter (library + notebook).

        Args:
            status: Optional status filter.

        Returns:
            Total count.
        """
        pass


