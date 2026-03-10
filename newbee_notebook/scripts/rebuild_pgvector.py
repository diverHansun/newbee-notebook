#!/usr/bin/env python3
"""Rebuild pgvector tables from converted markdown stored in runtime storage."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from llama_index.core import VectorStoreIndex

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from newbee_notebook.core.common.config import (
    get_embedding_provider,
    get_embeddings_config,
    get_pgvector_config_for_provider,
    get_storage_config,
)
from newbee_notebook.core.rag.embeddings import build_embedding
from newbee_notebook.core.rag.embeddings.registry import get_builder, get_registered_providers
from newbee_notebook.infrastructure.pgvector import PGVectorConfig, PGVectorStore
from newbee_notebook.scripts.rebuild_common import (
    get_rebuildable_documents,
    load_document_nodes,
)


def _build_embedding_for_provider(provider: str | None):
    """Build embedding model for an explicit provider or configured default."""
    if provider:
        return get_builder(provider)()
    return build_embedding()


def _get_enabled_embedding_providers() -> list[str]:
    """Return registry providers that are enabled in embeddings.yaml."""
    registered = get_registered_providers()
    embeddings_cfg = get_embeddings_config().get("embeddings", {})

    enabled: list[str] = []
    for provider in registered:
        provider_cfg = embeddings_cfg.get(provider, {})
        if isinstance(provider_cfg, dict) and provider_cfg.get("enabled") is False:
            continue
        enabled.append(provider)

    return enabled or registered


async def rebuild_pgvector_index(
    *,
    clear_only: bool = False,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    provider: str | None = None,
    document_ids: list[str] | None = None,
) -> None:
    """Rebuild pgvector from DB-tracked converted markdown content."""
    print("=" * 60)
    print("Rebuild pgvector Index")
    print("=" * 60)

    storage_config = get_storage_config()
    pg_config = storage_config.get("postgresql", {})

    effective_provider = provider or get_embedding_provider()
    print(f"\nUsing embedding provider: {effective_provider}")

    print("\n[1/4] Initializing embedding model...")
    embed_model = _build_embedding_for_provider(provider=effective_provider)

    embed_dim = (
        getattr(embed_model, "dimensions", None)
        or getattr(embed_model, "dimension", None)
        or 1024
    )
    embed_model_name = getattr(embed_model, "model_name", "unknown")
    print(f"Embedding model loaded: {embed_model_name} (dimension: {embed_dim})")

    pgvector_provider_cfg = get_pgvector_config_for_provider(effective_provider)
    config = PGVectorConfig(
        host=pg_config.get("host", "localhost"),
        port=pg_config.get("port", 5432),
        database=pg_config.get("database", "newbee_notebook"),
        user=pg_config.get("user", "postgres"),
        password=pg_config.get("password", ""),
        table_name=pgvector_provider_cfg["table_name"],
        embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
    )

    print(f"\nPostgreSQL: {config.host}:{config.port}/{config.database}")
    print(f"Table: {config.table_name}")
    print(f"Embedding dimension: {config.embedding_dimension}")

    print("\n[2/4] Initializing pgvector store...")
    store = PGVectorStore(config)
    await store.initialize()
    try:
        print("Connected to PostgreSQL")

        if clear_only:
            print("\n[3/4] Clearing existing data...")
            await store.clear()
            print("Data cleared successfully")
            print("\n" + "=" * 60)
            print("Done! (clear only mode)")
            return

        print("\n[3/4] Loading rebuildable documents from database...")
        docs = await get_rebuildable_documents(document_ids=document_ids)
        print(f"Found {len(docs)} document(s) with conversion artifacts")

        print("\n[4/4] Building pgvector index...")
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
    available_providers = _get_enabled_embedding_providers()

    parser = argparse.ArgumentParser(
        description="Rebuild pgvector index from DB-tracked markdown content",
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
    parser.add_argument(
        "--provider",
        type=str,
        choices=available_providers,
        default=None,
        help=(
            "Embedding provider to use "
            f"(default: from embeddings.yaml, available: {', '.join(available_providers)})"
        ),
    )

    args = parser.parse_args()

    asyncio.run(
        rebuild_pgvector_index(
            clear_only=args.clear_only,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            provider=args.provider,
            document_ids=args.document_id,
        )
    )


if __name__ == "__main__":
    main()
