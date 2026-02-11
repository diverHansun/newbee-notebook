"""
Newbee Notebook - Library Repository Interface
"""

from abc import ABC, abstractmethod
from typing import Optional
from newbee_notebook.domain.entities.library import Library


class LibraryRepository(ABC):
    """Repository interface for Library operations."""
    
    @abstractmethod
    async def get(self) -> Optional[Library]:
        """
        Get the Library.
        
        Returns:
            Library instance or None if not exists.
        """
        pass
    
    @abstractmethod
    async def create(self, library: Library) -> Library:
        """
        Create the Library.
        
        Args:
            library: Library instance to create.
            
        Returns:
            Created Library instance.
        """
        pass
    
    @abstractmethod
    async def update(self, library: Library) -> Library:
        """
        Update the Library.
        
        Args:
            library: Library instance with updated values.
            
        Returns:
            Updated Library instance.
        """
        pass
    
    @abstractmethod
    async def get_or_create(self) -> Library:
        """
        Get the Library, creating it if it doesn't exist.
        
        Returns:
            Library instance.
        """
        pass
    
    @abstractmethod
    async def increment_document_count(self, delta: int = 1) -> None:
        """
        Increment the document count.
        
        Args:
            delta: Amount to increment (default 1).
        """
        pass


