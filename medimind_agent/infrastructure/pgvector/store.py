"""PostgreSQL + pgvector vector store implementation.

This module provides a wrapper around LlamaIndex's PGVectorStore,
following the Dependency Inversion Principle (DIP) and Interface Segregation (ISP).
"""

import asyncio
from typing import List, Optional
from llama_index.core.schema import BaseNode
from llama_index.core.vector_stores.types import (
    VectorStoreQuery,
    VectorStoreQueryResult,
)
from llama_index.vector_stores.postgres import PGVectorStore as LlamaPGVectorStore

from medimind_agent.infrastructure.pgvector.config import PGVectorConfig


class PGVectorStore:
    """PostgreSQL + pgvector vector store wrapper.
    
    This class encapsulates LlamaIndex's PGVectorStore, providing a clean
    interface for vector operations while maintaining separation of concerns (SRP).
    
    Attributes:
        config: PGVectorConfig instance with connection parameters
        _store: Internal LlamaIndex PGVectorStore instance
    """
    
    def __init__(self, config: PGVectorConfig):
        """Initialize PGVectorStore.
        
        Args:
            config: PGVectorConfig instance with connection parameters
        """
        self.config = config
        self._store: Optional[LlamaPGVectorStore] = None
    
    def _ensure_initialized(self) -> None:
        """Ensure the store is initialized.
        
        Raises:
            RuntimeError: If store is not initialized
        """
        if self._store is None:
            raise RuntimeError(
                "PGVectorStore not initialized. Call initialize() first."
            )
    
    async def initialize(self) -> None:
        """Initialize the pgvector store asynchronously.
        
        Creates the vector extension and table if they don't exist.
        """
        self._store = LlamaPGVectorStore.from_params(
            host=self.config.host,
            port=str(self.config.port),
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            table_name=self.config.table_name,
            embed_dim=self.config.embedding_dimension,
        )
    
    def initialize_sync(self) -> None:
        """Initialize the pgvector store synchronously.
        
        Wrapper around async initialize for synchronous contexts.
        """
        asyncio.run(self.initialize())
    
    async def add_nodes(
        self,
        nodes: List[BaseNode],
        **kwargs,
    ) -> List[str]:
        """Add nodes to the vector store.
        
        Args:
            nodes: List of nodes to add
            **kwargs: Additional arguments to pass to the store
            
        Returns:
            List of node IDs that were added
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        return await self._store.async_add(nodes, **kwargs)
    
    async def query(
        self,
        query: VectorStoreQuery,
        **kwargs,
    ) -> VectorStoreQueryResult:
        """Query the vector store.
        
        Args:
            query: VectorStoreQuery instance with query parameters
            **kwargs: Additional arguments to pass to the store
            
        Returns:
            VectorStoreQueryResult with matching nodes
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        return await self._store.aquery(query, **kwargs)
    
    async def delete_nodes(
        self,
        node_ids: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """Delete nodes from the vector store.
        
        Args:
            node_ids: List of node IDs to delete, or None to delete all
            **kwargs: Additional arguments to pass to the store
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        if node_ids:
            await self._store.adelete_nodes(node_ids=node_ids, **kwargs)
        else:
            # Delete all nodes by clearing the table
            await self._store.aclear()
    
    async def clear(self) -> None:
        """Clear all nodes from the vector store.
        
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        await self._store.aclear()
    
    def get_llamaindex_store(self) -> LlamaPGVectorStore:
        """Get the underlying LlamaIndex PGVectorStore.
        
        This method is provided for compatibility with LlamaIndex APIs.
        
        Returns:
            LlamaPGVectorStore instance
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        return self._store

    @property
    def store(self) -> LlamaPGVectorStore:
        """Property alias for the underlying store (for compatibility)."""
        return self.get_llamaindex_store()
    
    async def close(self) -> None:
        """Close the database connection."""
        if self._store is not None:
            # PGVectorStore doesn't have explicit close method
            # Connection is managed by the database driver
            self._store = None


