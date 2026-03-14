"""Elasticsearch store implementation for BM25 text search.

This module provides a wrapper around LlamaIndex's ElasticsearchStore,
optimized for BM25 keyword-based retrieval.
"""

import asyncio
from typing import List, Optional
from llama_index.core.schema import BaseNode
from llama_index.core.vector_stores.types import (
    VectorStoreQuery,
    VectorStoreQueryResult,
    VectorStoreQueryMode,
)
from llama_index.vector_stores.elasticsearch import ElasticsearchStore as LlamaESStore
from elasticsearch.helpers.vectorstore import AsyncBM25Strategy

from newbee_notebook.infrastructure.elasticsearch.config import ElasticsearchConfig


class ElasticsearchStore:
    """Elasticsearch store wrapper for BM25 text search.
    
    This class encapsulates LlamaIndex's ElasticsearchStore configured for
    BM25 retrieval, following the Single Responsibility Principle (SRP).
    
    Attributes:
        config: ElasticsearchConfig instance with connection parameters
        _store: Internal LlamaIndex ElasticsearchStore instance
    """
    
    def __init__(self, config: ElasticsearchConfig):
        """Initialize ElasticsearchStore.
        
        Args:
            config: ElasticsearchConfig instance with connection parameters
        """
        self.config = config
        self._store: Optional[LlamaESStore] = None
    
    def _ensure_initialized(self) -> None:
        """Ensure the store is initialized.
        
        Raises:
            RuntimeError: If store is not initialized
        """
        if self._store is None:
            raise RuntimeError(
                "ElasticsearchStore not initialized. Call initialize() first."
            )
    
    async def initialize(self) -> None:
        """Initialize the Elasticsearch store asynchronously.
        
        Creates the index with BM25 configuration if it doesn't exist.
        """
        # Initialize with BM25 strategy for keyword search
        self._store = LlamaESStore(
            index_name=self.config.index_name,
            es_url=self.config.url,
            es_api_key=self.config.api_key,
            es_cloud_id=self.config.cloud_id,
            retrieval_strategy=AsyncBM25Strategy(),
            metadata_mappings={
                "source_document_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "doc_id": {"type": "keyword"},
                "ref_doc_id": {"type": "keyword"},
            },
        )
        if await self._store.client.indices.exists(index=self.config.index_name):
            await self._store.client.indices.put_mapping(
                index=self.config.index_name,
                body={
                    "properties": {
                        "metadata": {
                            "properties": {
                                "source_document_id": {"type": "keyword"},
                            }
                        }
                    }
                },
            )
    
    def initialize_sync(self) -> None:
        """Initialize the Elasticsearch store synchronously.
        
        Wrapper around async initialize for synchronous contexts.
        """
        asyncio.run(self.initialize())
    
    async def add_nodes(
        self,
        nodes: List[BaseNode],
        **kwargs,
    ) -> List[str]:
        """Add nodes to the Elasticsearch index.
        
        Args:
            nodes: List of nodes to add
            **kwargs: Additional arguments to pass to the store
            
        Returns:
            List of node IDs that were added
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        return self._store.add(nodes, **kwargs)
    
    async def query(
        self,
        query: VectorStoreQuery,
        **kwargs,
    ) -> VectorStoreQueryResult:
        """Query the Elasticsearch index using BM25.
        
        Args:
            query: VectorStoreQuery instance with query parameters
            **kwargs: Additional arguments to pass to the store
            
        Returns:
            VectorStoreQueryResult with matching nodes
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        
        # Ensure we're using TEXT_SEARCH mode for BM25
        query.mode = VectorStoreQueryMode.TEXT_SEARCH
        
        return await self._store.aquery(query, **kwargs)
    
    async def delete_nodes(
        self,
        node_ids: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """Delete nodes from the Elasticsearch index.
        
        Args:
            node_ids: List of node IDs to delete, or None to delete all
            **kwargs: Additional arguments to pass to the store
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        
        if node_ids:
            self._store.delete_nodes(node_ids=node_ids, **kwargs)
        else:
            # Clear the entire index
            await self._store.aclear()
    
    async def clear(self) -> None:
        """Clear all nodes from the Elasticsearch index.
        
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        await self._store.aclear()
    
    def get_llamaindex_store(self) -> LlamaESStore:
        """Get the underlying LlamaIndex ElasticsearchStore.
        
        This method is provided for compatibility with LlamaIndex APIs.
        
        Returns:
            ElasticsearchStore instance
            
        Raises:
            RuntimeError: If store is not initialized
        """
        self._ensure_initialized()
        return self._store

    @property
    def store(self) -> LlamaESStore:
        """Property alias for the underlying store (for compatibility)."""
        return self.get_llamaindex_store()
    
    async def close(self) -> None:
        """Close the Elasticsearch connection."""
        if self._store is not None:
            self._store.close()
            self._store = None


