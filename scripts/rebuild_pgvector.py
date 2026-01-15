#!/usr/bin/env python3
"""Rebuild pgvector index from documents.

This script:
1. Loads documents from data/documents/
2. Clears existing pgvector data
3. Builds new index with embeddings

Usage:
    python scripts/rebuild_pgvector.py
    python scripts/rebuild_pgvector.py --documents-dir /path/to/docs
    python scripts/rebuild_pgvector.py --clear-only
"""

import sys
import os
import argparse
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.config import get_documents_directory, get_storage_config
from src.rag.embeddings import build_embedding
from src.infrastructure.pgvector import PGVectorStore, PGVectorConfig
from src.engine.index_builder import IndexBuilder
from llama_index.core import StorageContext, VectorStoreIndex


async def rebuild_pgvector_index(
    documents_dir: str,
    clear_only: bool = False,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> None:
    """Rebuild pgvector index from documents.
    
    Args:
        documents_dir: Directory containing documents
        clear_only: If True, only clear existing data
        chunk_size: Text chunk size
        chunk_overlap: Overlap between chunks
    """
    print("=" * 60)
    print("Rebuild pgvector Index")
    print("=" * 60)
    
    # Load storage config
    storage_config = get_storage_config()
    pg_config = storage_config.get("postgresql", {})
    pgvector_config = storage_config.get("pgvector", {})
    
    # Step 1: Initialize embedding model early to align table dimension
    print("\n[1/4] Initializing embedding model...")
    embed_model = build_embedding()
    embed_dim = getattr(embed_model, "dimensions", None) or getattr(embed_model, "dimension", None) or 1024
    print(f"Embedding model loaded (dimension: {embed_dim})")
    
    # Create pgvector config (use embedding dimension to avoid mismatch)
    config = PGVectorConfig(
        host=pg_config.get("host", "localhost"),
        port=pg_config.get("port", 5432),
        database=pg_config.get("database", "medimind"),
        user=pg_config.get("user", "postgres"),
        password=pg_config.get("password", ""),
        table_name=pgvector_config.get("table_name", "documents"),
        embedding_dimension=embed_dim,
    )
    
    print(f"\nPostgreSQL: {config.host}:{config.port}/{config.database}")
    print(f"Table: {config.table_name}")
    
    # Initialize store
    print("\n[2/4] Initializing pgvector store...")
    store = PGVectorStore(config)
    await store.initialize()
    print("Connected to PostgreSQL")
    
    if clear_only:
        print("\n[3/4] Clearing existing data...")
        await store.clear()
        print("Data cleared successfully")
        print("\n" + "=" * 60)
        print("Done! (clear only mode)")
        return
    
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
    print("\n[4/4] Building pgvector index...")
    print("Clearing existing data...")
    await store.clear()
    
    print("Adding nodes to index...")
    storage_context = StorageContext.from_defaults(
        vector_store=store.get_llamaindex_store()
    )
    VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )
    
    print("\n" + "=" * 60)
    print(f"Success! Indexed {len(nodes)} chunks to pgvector")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild pgvector index from documents",
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
    asyncio.run(rebuild_pgvector_index(
        documents_dir=documents_dir,
        clear_only=args.clear_only,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    ))


if __name__ == "__main__":
    main()
