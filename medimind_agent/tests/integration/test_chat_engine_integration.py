"""Test script for ChatEngine implementation with memory.

This script tests the complete flow:
1. Build embeddings
2. Create index from sample documents
3. Build LLM and memory
4. Create ChatEngine
5. Create Agent
6. Test multi-turn conversation
"""

import os
from pathlib import Path

# Setup path
os.chdir(str(Path(__file__).parent))

from medimind_agent.core.llm.zhipu import build_llm
from medimind_agent.core.rag.embeddings.zhipu import build_embedding
from medimind_agent.core.rag.indexing import build_index_if_not_exists
from medimind_agent.core.memory import build_chat_memory
from medimind_agent.core.rag.generation.chat_engine import build_chat_engine
from medimind_agent.core.agent.agent import MediMindAgent
from medimind_agent.core.common.config import get_documents_directory, get_index_directory


def main():
    """Run ChatEngine integration test."""
    print("=" * 60)
    print("ChatEngine with Memory Integration Test")
    print("=" * 60)

    # Setup paths
    docs_dir = get_documents_directory()
    index_dir = get_index_directory()

    print(f"\n1. Loading documents from: {docs_dir}")
    print(f"   Index directory: {index_dir}")

    # Build embeddings
    print("\n2. Building embeddings...")
    embed_model = build_embedding()
    print(f"   [OK] Embedding model: {embed_model.model_name}")
    print(f"   [OK] Dimension: {embed_model.dimensions}")

    # Build or load index
    print("\n3. Building/loading index...")
    index = build_index_if_not_exists(
        documents_dir=docs_dir,
        embed_model=embed_model,
        persist_dir=index_dir,
    )
    print(f"   [OK] Index ready")

    # Build LLM
    print("\n4. Building LLM...")
    llm = build_llm()
    print(f"   [OK] LLM ready: glm-4-plus")

    # Build Memory
    print("\n5. Building chat memory...")
    memory = build_chat_memory(llm=llm, token_limit=64000)
    print(f"   [OK] Memory buffer: 64000 tokens")

    # Build ChatEngine
    print("\n6. Building ChatEngine...")
    chat_engine = build_chat_engine(
        index=index,
        llm=llm,
        memory=memory,
        similarity_top_k=10,
        similarity_cutoff=0.1,
    )
    print(f"   [OK] ChatEngine ready (mode: condense_plus_context)")

    # Create Agent
    print("\n7. Creating MediMindAgent...")
    agent = MediMindAgent(llm=llm, chat_engine=chat_engine)
    print(f"   [OK] Agent ready")

    # Test multi-turn conversation
    print("\n" + "=" * 60)
    print("Testing Multi-Turn Conversation")
    print("=" * 60)

    try:
        # First turn
        print("\nUser: What is diabetes?")
        response1 = agent.chat("What is diabetes?")
        print(f"\nAssistant:\n{response1}")

        # Second turn (with context)
        print("\n" + "-" * 60)
        print("\nUser: What are its common symptoms?")
        response2 = agent.chat("What are its common symptoms?")
        print(f"\nAssistant:\n{response2}")

        # Third turn
        print("\n" + "-" * 60)
        print("\nUser: Tell me about cardiovascular health.")
        response3 = agent.chat("Tell me about cardiovascular health.")
        print(f"\nAssistant:\n{response3}")

        print("\n" + "=" * 60)
        print("[SUCCESS] Test completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


