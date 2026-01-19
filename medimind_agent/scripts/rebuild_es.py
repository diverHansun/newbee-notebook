#!/usr/bin/env python3
"""Rebuild Elasticsearch index from documents.

This script:
1. Loads documents from data/documents/
2. Clears existing Elasticsearch index
3. Builds new index with BM25 text search

Usage:
    python scripts/rebuild_es.py
    python scripts/rebuild_es.py --documents-dir /path/to/docs
    python scripts/rebuild_es.py --clear-only
"""

import sys
import os
import argparse
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from medimind_agent.core.common.config import get_documents_directory, get_storage_config
from medimind_agent.core.rag.embeddings import build_embedding
from medimind_agent.infrastructure.elasticsearch import ElasticsearchStore, ElasticsearchConfig
from medimind_agent.core.engine.index_builder import IndexBuilder


async def rebuild_es_index(
    documents_dir: str,
    clear_only: bool = False,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> None:
    """Rebuild Elasticsearch index from documents.
    
    Args:
        documents_dir: Directory containing documents
        clear_only: If True, only clear existing data
        chunk_size: Text chunk size
        chunk_overlap: Overlap between chunks
    """
    print("=" * 60)
    print("Rebuild Elasticsearch Index")
    print("=" * 60)
    
    # Load storage config
    storage_config = get_storage_config()
    es_config = storage_config.get("elasticsearch", {})
    
    # Create ES config
    config = ElasticsearchConfig(
        url=es_config.get("url", "http://localhost:9200"),
        index_name=es_config.get("index_name", "medimind_docs"),
    )
    
    print(f"\nElasticsearch: {config.url}")
    print(f"Index: {config.index_name}")
    
    # Initialize store
    print("\n[1/4] Initializing Elasticsearch store...")
    store = ElasticsearchStore(config)
    await store.initialize()
    print("Connected to Elasticsearch")
    
    if clear_only:
        print("\n[2/4] Clearing existing data...")
        await store.clear()
        print("Data cleared successfully")
        print("\n" + "=" * 60)
        print("Done! (clear only mode)")
        return
    
    # Initialize embedding model (needed for IndexBuilder)
    print("\n[2/4] Initializing embedding model...")
    embed_model = build_embedding()
    print(f"Embedding model loaded (dimension: {embed_model.dimensions})")
    
    # Load and parse documents
    print(f"\n[3/4] Loading documents from {documents_dir}...")
    builder = IndexBuilder(
        embed_model=embed_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    
    try:
        nodes = builder.load_and_parse_documents(
            documents_dir=documents_dir,
            show_progress=True,
        )
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print(f"Please add documents to: {documents_dir}")
        sys.exit(1)
    
    # Clear existing data and build index
    print("\n[4/4] Building Elasticsearch index...")
    print("Clearing existing data...")
    await store.clear()
    
    print("Adding nodes to index...")
    await store.add_nodes(nodes)
    
    print("\n" + "=" * 60)
    print(f"Success! Indexed {len(nodes)} chunks to Elasticsearch")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild Elasticsearch index from documents",
    )
    parser.add_argument(
        "--documents-dir",
        type=str,
        default=None,
        help="Directory containing documents (default: from config)",
    )
    parser.add_argument(
        "--clear-only",
        action="store_true",
        help="Only clear existing data, don't rebuild",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Text chunk size (default: 512)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Overlap between chunks (default: 50)",
    )
    
    args = parser.parse_args()
    
    # Get documents directory
    documents_dir = args.documents_dir or get_documents_directory()
    
    # Run rebuild
    asyncio.run(rebuild_es_index(
        documents_dir=documents_dir,
        clear_only=args.clear_only,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    ))


if __name__ == "__main__":
    main()


