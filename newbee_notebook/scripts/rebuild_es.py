#!/usr/bin/env python3
"""Rebuild the Elasticsearch index from converted markdown stored in runtime storage."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from llama_index.core import VectorStoreIndex

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from newbee_notebook.core.common.config_db import sync_embedding_runtime_env_from_db
from newbee_notebook.core.common.config import get_storage_config
from newbee_notebook.core.rag.embeddings import build_embedding
from newbee_notebook.infrastructure.elasticsearch import ElasticsearchConfig, ElasticsearchStore
from newbee_notebook.infrastructure.persistence.database import get_database
from newbee_notebook.scripts.rebuild_common import (
    get_rebuildable_documents,
    load_document_nodes,
)


async def rebuild_es_index(
    *,
    clear_only: bool = False,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    document_ids: list[str] | None = None,
) -> None:
    """Rebuild Elasticsearch from DB-tracked converted markdown content."""
    print("=" * 60)
    print("Rebuild Elasticsearch Index")
    print("=" * 60)

    storage_config = get_storage_config()
    es_config = storage_config.get("elasticsearch", {})
    config = ElasticsearchConfig(
        url=es_config.get("url", "http://localhost:9200"),
        index_name=es_config.get("index_name", "newbee_notebook_docs"),
        api_key=es_config.get("api_key"),
        cloud_id=es_config.get("cloud_id"),
    )

    print(f"\nElasticsearch: {config.url}")
    print(f"Index: {config.index_name}")

    print("\n[1/4] Initializing Elasticsearch store...")
    store = ElasticsearchStore(config)
    await store.initialize()
    try:
        print("Connected to Elasticsearch")

        if clear_only:
            print("\n[2/4] Clearing existing data...")
            await store.clear()
            print("Data cleared successfully")
            print("\n" + "=" * 60)
            print("Done! (clear only mode)")
            return

        print("\n[2/4] Initializing embedding model...")
        db = await get_database()
        async with db.session() as session:
            embedding_cfg = await sync_embedding_runtime_env_from_db(session)
        print(
            "Embedding runtime config: "
            f"provider={embedding_cfg['provider']} source={embedding_cfg.get('source', 'unknown')}"
        )
        embed_model = build_embedding()
        print(f"Embedding model loaded (dimension: {getattr(embed_model, 'dimensions', 'unknown')})")

        print("\n[3/4] Loading rebuildable documents from database...")
        docs = await get_rebuildable_documents(document_ids=document_ids)
        print(f"Found {len(docs)} document(s) with conversion artifacts")

        print("\n[4/4] Building Elasticsearch index...")
        print("Clearing existing data...")
        await store.clear()

        index = VectorStoreIndex.from_vector_store(
            vector_store=store.store,
            embed_model=embed_model,
        )

        indexed_chunks = 0
        for idx, doc in enumerate(docs, start=1):
            nodes = await load_document_nodes(
                doc,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if not nodes:
                print(f"Skipping {doc.document_id}: no nodes generated")
                continue
            index.insert_nodes(nodes)
            indexed_chunks += len(nodes)
            print(
                f"[{idx}/{len(docs)}] Indexed {doc.document_id} "
                f"({len(nodes)} chunk(s))"
            )

        print("\n" + "=" * 60)
        print(f"Success! Indexed {indexed_chunks} chunks from {len(docs)} document(s)")
        print("=" * 60)
    finally:
        await store.close()


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild Elasticsearch index from DB-tracked markdown content",
    )
    parser.add_argument(
        "--document-id",
        action="append",
        default=None,
        help="Restrict rebuild to one or more document IDs",
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

    asyncio.run(
        rebuild_es_index(
            clear_only=args.clear_only,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            document_ids=args.document_id,
        )
    )


if __name__ == "__main__":
    main()
