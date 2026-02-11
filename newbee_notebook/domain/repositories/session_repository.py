"""
Newbee Notebook - Session Repository Interface
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from newbee_notebook.domain.entities.session import Session


class SessionRepository(ABC):
    """Repository interface for Session operations."""
    
    @abstractmethod
    async def get(self, session_id: str) -> Optional[Session]:
        """
        Get a Session by ID.
        
        Args:
            session_id: Session unique identifier.
            
        Returns:
            Session instance or None if not found.
        """
        pass
    
    @abstractmethod
    async def list_by_notebook(
        self,
        notebook_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Session]:
        """
        List Sessions in a Notebook, ordered by updated_at DESC.
        
        Args:
            notebook_id: Notebook unique identifier.
            limit: Maximum number of results.
            offset: Number of results to skip.
            
        Returns:
            List of Session instances.
        """
        pass
    
    @abstractmethod
    async def get_latest_by_notebook(self, notebook_id: str) -> Optional[Session]:
        """
        Get the most recently updated Session in a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Session instance or None if no sessions exist.
        """
        pass
    
    @abstractmethod
    async def count_by_notebook(self, notebook_id: str) -> int:
        """
        Count Sessions in a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Total count.
        """
        pass
    
    @abstractmethod
    async def create(self, session: Session) -> Session:
        """
        Create a Session.
        
        Args:
            session: Session instance to create.
            
        Returns:
            Created Session instance.
        """
        pass
    
    @abstractmethod
    async def update(self, session: Session) -> Session:
        """
        Update a Session.
        
        Args:
            session: Session instance with updated values.
            
        Returns:
            Updated Session instance.
        """
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """
        Delete a Session.
        
        Args:
            session_id: Session unique identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    async def delete_by_notebook(self, notebook_id: str) -> int:
        """
        Delete all Sessions in a Notebook.
        
        Args:
            notebook_id: Notebook unique identifier.
            
        Returns:
            Number of sessions deleted.
        """
        pass
    
    @abstractmethod
    async def increment_message_count(self, session_id: str, delta: int = 1) -> None:
        """
        Increment the message count.
        
        Args:
            session_id: Session unique identifier.
            delta: Amount to increment (default 1).
        """
        pass
    
    @abstractmethod
    async def update_context_summary(self, session_id: str, summary: str) -> None:
        """
        Update the context summary.
        
        Args:
            session_id: Session unique identifier.
            summary: New context summary.
        """
        pass


