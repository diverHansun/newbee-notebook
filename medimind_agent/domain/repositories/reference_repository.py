"""
MediMind Agent - Reference Repository Interfaces
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from medimind_agent.domain.entities.reference import NotebookDocumentRef, Reference


class NotebookDocumentRefRepository(ABC):
    """Repository interface for Notebook-Document reference operations."""
    
    @abstractmethod
    async def get(self, reference_id: str) -> Optional[NotebookDocumentRef]:
        """
        Get a reference by ID.
        
        Args:
            reference_id: Reference unique identifier.
            
        Returns:
            NotebookDocumentRef instance or None if not found.
        """
        pass
    
    @abstractmethod
    async def get_by_notebook_and_document(
        self, 
        notebook_id: str, 
        document_id: str
    ) -> Optional[NotebookDocumentRef]:
        """
        Get a reference by Notebook and Document IDs.
        
        Args:
            notebook_id: Notebook unique identifier.
            document_id: Document unique identifier.
            
        Returns:
            NotebookDocumentRef instance or None if not found.
        """
        pass
    
    @abstractmethod
    async def list_by_notebook(self, notebook_id: str) -> List[NotebookDocumentRef]:
        """
        List all references for a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            List of NotebookDocumentRef instances.
        """
        pass
    
    @abstractmethod
    async def list_by_document(self, document_id: str) -> List[NotebookDocumentRef]:
        """
        List all references for a Document.
        
        Args:
            document_id: Document unique identifier.
            
        Returns:
            List of NotebookDocumentRef instances.
        """
        pass
    
    @abstractmethod
    async def count_by_document(self, document_id: str) -> int:
        """
        Count how many Notebooks reference a Document.
        
        Args:
            document_id: Document unique identifier.
            
        Returns:
            Reference count.
        """
        pass
    
    @abstractmethod
    async def create(self, ref: NotebookDocumentRef) -> NotebookDocumentRef:
        """
        Create a reference.
        
        Args:
            ref: NotebookDocumentRef instance to create.
            
        Returns:
            Created NotebookDocumentRef instance.
        """
        pass
    
    @abstractmethod
    async def delete(self, reference_id: str) -> bool:
        """
        Delete a reference.
        
        Args:
            reference_id: Reference unique identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    async def delete_by_notebook(self, notebook_id: str) -> int:
        """
        Delete all references for a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Number of references deleted.
        """
        pass
    
    @abstractmethod
    async def delete_by_document(self, document_id: str) -> int:
        """
        Delete all references for a Document.
        
        Args:
            document_id: Document unique identifier.
            
        Returns:
            Number of references deleted.
        """
        pass


class ReferenceRepository(ABC):
    """Repository interface for citation Reference operations."""
    
    @abstractmethod
    async def get(self, reference_id: str) -> Optional[Reference]:
        """
        Get a Reference by ID.
        
        Args:
            reference_id: Reference unique identifier.
            
        Returns:
            Reference instance or None if not found.
        """
        pass
    
    @abstractmethod
    async def list_by_message(
        self, 
        session_id: str, 
        message_id: int
    ) -> List[Reference]:
        """
        List all References for a Message.
        
        Args:
            session_id: Session unique identifier.
            message_id: Message ID.
            
        Returns:
            List of Reference instances.
        """
        pass
    
    @abstractmethod
    async def list_by_session(self, session_id: str) -> List[Reference]:
        """
        List all References in a Session.
        
        Args:
            session_id: Session unique identifier.
            
        Returns:
            List of Reference instances.
        """
        pass
    
    @abstractmethod
    async def create(self, reference: Reference) -> Reference:
        """
        Create a Reference.
        
        Args:
            reference: Reference instance to create.
            
        Returns:
            Created Reference instance.
        """
        pass
    
    @abstractmethod
    async def create_batch(self, references: List[Reference]) -> List[Reference]:
        """
        Create multiple References.
        
        Args:
            references: List of Reference instances to create.
            
        Returns:
            List of created Reference instances.
        """
        pass
    
    @abstractmethod
    async def delete(self, reference_id: str) -> bool:
        """
        Delete a Reference.
        
        Args:
            reference_id: Reference unique identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    async def delete_by_session(self, session_id: str) -> int:
        """
        Delete all References in a Session.
        
        Args:
            session_id: Session unique identifier.
            
        Returns:
            Number of references deleted.
        """
        pass


