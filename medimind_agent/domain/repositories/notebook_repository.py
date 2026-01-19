"""
MediMind Agent - Notebook Repository Interface
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from medimind_agent.domain.entities.notebook import Notebook


class NotebookRepository(ABC):
    """Repository interface for Notebook operations."""
    
    @abstractmethod
    async def get(self, notebook_id: str) -> Optional[Notebook]:
        """
        Get a Notebook by ID.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Notebook instance or None if not found.
        """
        pass
    
    @abstractmethod
    async def list(
        self, 
        limit: int = 20, 
        offset: int = 0,
        order_by: str = "updated_at",
        desc: bool = True
    ) -> List[Notebook]:
        """
        List all Notebooks with pagination.
        
        Args:
            limit: Maximum number of results.
            offset: Number of results to skip.
            order_by: Field to order by.
            desc: Sort descending if True.
            
        Returns:
            List of Notebook instances.
        """
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """
        Count total Notebooks.
        
        Returns:
            Total count.
        """
        pass
    
    @abstractmethod
    async def create(self, notebook: Notebook) -> Notebook:
        """
        Create a Notebook.
        
        Args:
            notebook: Notebook instance to create.
            
        Returns:
            Created Notebook instance.
        """
        pass
    
    @abstractmethod
    async def update(self, notebook: Notebook) -> Notebook:
        """
        Update a Notebook.
        
        Args:
            notebook: Notebook instance with updated values.
            
        Returns:
            Updated Notebook instance.
        """
        pass
    
    @abstractmethod
    async def delete(self, notebook_id: str) -> bool:
        """
        Delete a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    async def increment_session_count(self, notebook_id: str, delta: int = 1) -> None:
        """
        Increment the session count.
        
        Args:
            notebook_id: Notebook unique identifier.
            delta: Amount to increment (default 1).
        """
        pass
    
    @abstractmethod
    async def increment_document_count(self, notebook_id: str, delta: int = 1) -> None:
        """
        Increment the document count.
        
        Args:
            notebook_id: Notebook unique identifier.
            delta: Amount to increment (default 1).
        """
        pass


