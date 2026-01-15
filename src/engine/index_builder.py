"""Index builder for pgvector and Elasticsearch.

This module provides utilities for building and managing indexes
for different vector stores and search backends.
"""

import os
from typing import Optional, List
from llama_index.core import VectorStoreIndex, StorageContext, Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import TextNode

from src.rag.document_loader import load_documents
from src.infrastructure.pgvector import PGVectorStore, PGVectorConfig
from src.infrastructure.elasticsearch import ElasticsearchStore, ElasticsearchConfig


class IndexBuilder:
    """Builder for creating and managing vector store indexes.
    
    This class provides unified methods for:
    - Loading and processing documents
    - Building pgvector indexes
    - Building Elasticsearch indexes
    """
    
    def __init__(
        self,
        embed_model: BaseEmbedding,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """Initialize IndexBuilder.
        
        Args:
            embed_model: Embedding model for vectorization
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self._embed_model = embed_model
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        
        self._node_parser = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    
    def load_and_parse_documents(
        self,
        documents_dir: str,
        show_progress: bool = True,
    ) -> List[TextNode]:
        """Load documents and parse into nodes.
        
        Args:
            documents_dir: Directory containing documents
            show_progress: Show progress during loading
            
        Returns:
            List of parsed text nodes
            
        Raises:
            FileNotFoundError: If documents directory is empty
        """
        # Load documents
        documents = load_documents(
            input_dir=documents_dir,
            recursive=True,
        )
        
        if not documents:
            raise FileNotFoundError(f"No documents found in {documents_dir}")
        
        if show_progress:
            print(f"Loaded {len(documents)} documents")
        
        # Parse into nodes
        nodes = self._node_parser.get_nodes_from_documents(
            documents,
            show_progress=show_progress,
        )
        
        if show_progress:
            print(f"Created {len(nodes)} text chunks")
        
        return nodes
    
    async def build_pgvector_index(
        self,
        nodes: List[TextNode],
        config: Optional[PGVectorConfig] = None,
        show_progress: bool = True,
    ) -> VectorStoreIndex:
        """Build a pgvector-backed index.
        
        Args:
            nodes: Text nodes to index
            config: pgvector configuration
            show_progress: Show progress during indexing
            
        Returns:
            VectorStoreIndex backed by pgvector
        """
        if config is None:
            config = PGVectorConfig()
        
        if show_progress:
            print("Initializing pgvector store...")
        
        # Initialize pgvector store
        pgvector_store = PGVectorStore(config)
        await pgvector_store.initialize()
        
        if show_progress:
            print("Building pgvector index...")
        
        # Create storage context
        storage_context = StorageContext.from_defaults(
            vector_store=pgvector_store.store,
        )
        
        # Create index
        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=self._embed_model,
            show_progress=show_progress,
        )
        
        if show_progress:
            print(f"pgvector index built with {len(nodes)} nodes")
        
        return index
    
    async def build_es_index(
        self,
        nodes: List[TextNode],
        config: Optional[ElasticsearchConfig] = None,
        show_progress: bool = True,
    ) -> VectorStoreIndex:
        """Build an Elasticsearch-backed index.
        
        Args:
            nodes: Text nodes to index
            config: Elasticsearch configuration
            show_progress: Show progress during indexing
            
        Returns:
            VectorStoreIndex backed by Elasticsearch
        """
        if config is None:
            config = ElasticsearchConfig()
        
        if show_progress:
            print("Initializing Elasticsearch store...")
        
        # Initialize ES store
        es_store = ElasticsearchStore(config)
        await es_store.initialize()
        
        if show_progress:
            print("Building Elasticsearch index...")
        
        # Create storage context
        storage_context = StorageContext.from_defaults(
            vector_store=es_store.store,
        )
        
        # Create index
        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=self._embed_model,
            show_progress=show_progress,
        )
        
        if show_progress:
            print(f"Elasticsearch index built with {len(nodes)} nodes")
        
        return index
    
    def build_pgvector_index_sync(
        self,
        nodes: List[TextNode],
        config: Optional[PGVectorConfig] = None,
        show_progress: bool = True,
    ) -> VectorStoreIndex:
        """Synchronous version of build_pgvector_index."""
        import asyncio
        return asyncio.run(self.build_pgvector_index(nodes, config, show_progress))
    
    def build_es_index_sync(
        self,
        nodes: List[TextNode],
        config: Optional[ElasticsearchConfig] = None,
        show_progress: bool = True,
    ) -> VectorStoreIndex:
        """Synchronous version of build_es_index."""
        import asyncio
        return asyncio.run(self.build_es_index(nodes, config, show_progress))


async def load_pgvector_index(
    embed_model: BaseEmbedding,
    config: Optional[PGVectorConfig] = None,
) -> VectorStoreIndex:
    """Load an existing pgvector index.
    
    Args:
        embed_model: Embedding model
        config: pgvector configuration
        
    Returns:
        VectorStoreIndex backed by pgvector
    """
    if config is None:
        config = PGVectorConfig()
    
    pgvector_store = PGVectorStore(config)
    await pgvector_store.initialize()
    
    index = VectorStoreIndex.from_vector_store(
        vector_store=pgvector_store.store,
        embed_model=embed_model,
    )
    
    return index


async def load_es_index(
    embed_model: BaseEmbedding,
    config: Optional[ElasticsearchConfig] = None,
) -> VectorStoreIndex:
    """Load an existing Elasticsearch index.
    
    Args:
        embed_model: Embedding model
        config: Elasticsearch configuration
        
    Returns:
        VectorStoreIndex backed by Elasticsearch
    """
    if config is None:
        config = ElasticsearchConfig()
    
    es_store = ElasticsearchStore(config)
    await es_store.initialize()
    
    index = VectorStoreIndex.from_vector_store(
        vector_store=es_store.store,
        embed_model=embed_model,
    )
    
    return index


def load_pgvector_index_sync(
    embed_model: BaseEmbedding,
    config: Optional[PGVectorConfig] = None,
) -> VectorStoreIndex:
    """Synchronous version of load_pgvector_index."""
    import asyncio
    return asyncio.run(load_pgvector_index(embed_model, config))


def load_es_index_sync(
    embed_model: BaseEmbedding,
    config: Optional[ElasticsearchConfig] = None,
) -> VectorStoreIndex:
    """Synchronous version of load_es_index."""
    import asyncio
    return asyncio.run(load_es_index(embed_model, config))
