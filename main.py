#!/usr/bin/env python3
"""Main entry point for Newbee Notebook.

This script provides a multi-mode medical Q&A assistant with:
- Chat mode: Free conversation with web search and knowledge base tools
- Ask mode: Deep Q&A with RAG and hybrid retrieval
- Conclude mode: Document summarization
- Explain mode: Concept explanation

Usage:
    python main.py              # Start with default Chat mode
    python main.py --mode ask   # Start with Ask mode
"""

import sys
import os
import io
import logging
import argparse
import asyncio

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from newbee_notebook.core.llm.zhipu import build_llm
from newbee_notebook.core.rag.embeddings import build_embedding
from newbee_notebook.core.common.config import (
    get_documents_directory,
    get_storage_config,
    get_embedding_provider,
    get_pgvector_config_for_provider,
)
from newbee_notebook.core.engine import (
    ModeType,
    SessionManager,
    parse_mode_from_input,
    get_mode_help,
    load_pgvector_index,
    load_es_index,
)
from newbee_notebook.infrastructure.pgvector import PGVectorConfig
from newbee_notebook.infrastructure.elasticsearch import ElasticsearchConfig
from newbee_notebook.domain.repositories.session_repository import SessionRepository
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.value_objects.mode_type import MessageRole


class InMemorySessionRepo(SessionRepository):
    def __init__(self):
        self._sessions = {}

    async def get(self, session_id: str):
        return self._sessions.get(session_id)

    async def list_by_notebook(self, notebook_id: str, limit: int = 20, offset: int = 0):
        return []

    async def get_latest_by_notebook(self, notebook_id: str):
        return None

    async def count_by_notebook(self, notebook_id: str) -> int:
        return 0

    async def create(self, session: Session) -> Session:
        self._sessions[session.session_id] = session
        return session

    async def update(self, session: Session) -> Session:
        self._sessions[session.session_id] = session
        return session

    async def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    async def delete_by_notebook(self, notebook_id: str) -> int:
        return 0

    async def increment_message_count(self, session_id: str, delta: int = 1) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].message_count += delta

    async def update_context_summary(self, session_id: str, summary: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].context_summary = summary


class InMemoryMessageRepo(MessageRepository):
    def __init__(self):
        self._messages = []

    async def create(self, message: Message) -> Message:
        message.message_id = len(self._messages) + 1
        self._messages.append(message)
        return message

    async def create_batch(self, messages):
        return [await self.create(m) for m in messages]

    async def list_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        modes=None,
    ):
        rows = [m for m in self._messages if m.session_id == session_id]
        if modes is not None:
            mode_values = {mode.value if hasattr(mode, "value") else str(mode) for mode in modes}
            if not mode_values:
                return []
            rows = [m for m in rows if (m.mode.value if hasattr(m.mode, "value") else str(m.mode)) in mode_values]
        return rows[offset: offset + limit]

    async def count_by_session(self, session_id: str, modes=None) -> int:
        rows = [m for m in self._messages if m.session_id == session_id]
        if modes is not None:
            mode_values = {mode.value if hasattr(mode, "value") else str(mode) for mode in modes}
            if not mode_values:
                return 0
            rows = [m for m in rows if (m.mode.value if hasattr(m.mode, "value") else str(m.mode)) in mode_values]
        return len(rows)


def print_banner():
    """Print application banner."""
    print("=" * 60)
    print("Newbee Notebook - Multi-Mode Medical Q&A Assistant")
    print("=" * 60)
    print("Commands: /help, /mode <name>, /status, /reset, /new, /quit")
    print("-" * 60)


def print_status(session_manager: SessionManager):
    """Print current session status."""
    status = session_manager.get_status()
    print("\n--- Session Status ---")
    print(f"Session ID: {status['session_id'] or 'Local (not persisted)'}")
    print(f"Current Mode: {status['current_mode']}")
    print(f"Mode: {status['mode_info'].get('name', 'Unknown')}")
    print(f"Description: {status['mode_info'].get('description', '')}")
    print(f"Has Memory: {status['mode_info'].get('has_memory', False)}")
    print(f"Messages in Memory: {status['memory_messages']}")
    print("----------------------")


async def initialize_services(args):
    """Initialize all required services.
    
    Args:
        args: Command line arguments
        
    Returns:
        Tuple of (llm, pgvector_index, es_index, session_repo, message_repo)
    """
    print("\n[1/5] Initializing LLM...")
    llm = build_llm()
    print("LLM initialized")
    
    print("\n[2/5] Initializing embedding model...")
    embed_model = build_embedding()
    print(f"Embedding model initialized (dimension: {embed_model.dimensions})")
    
    # Load storage config
    storage_config = get_storage_config()
    pg_config = storage_config.get("postgresql", {})
    pgvector_cfg = storage_config.get("pgvector", {})
    session_cfg = storage_config.get("chat_sessions", {})
    
    # Initialize pgvector index (required for ask, conclude, explain)
    pgvector_index = None
    if not args.no_pgvector:
        print("\n[3/5] Connecting to pgvector...")
        try:
            # Get provider-specific pgvector configuration
            provider = get_embedding_provider()
            pgvector_provider_cfg = get_pgvector_config_for_provider(provider)

            config = PGVectorConfig(
                host=pg_config.get("host", "localhost"),
                port=pg_config.get("port", 5432),
                database=pg_config.get("database", "newbee_notebook"),
                user=pg_config.get("user", "postgres"),
                password=pg_config.get("password", ""),
                # Use provider-specific table and dimension
                table_name=pgvector_provider_cfg["table_name"],
                embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
            )

            pgvector_index = await load_pgvector_index(embed_model, config)
            print(f"pgvector connected (provider: {provider}, table: {config.table_name}, dim: {config.embedding_dimension})")
        except Exception as e:
            print(f"Warning: Could not connect to pgvector: {e}")
            print("RAG modes (ask, conclude, explain) may not work")
    else:
        print("\n[3/5] Skipping pgvector (--no-pgvector)")
    
    # Initialize Elasticsearch index (required for ask mode hybrid retrieval)
    es_index = None
    if not args.no_elasticsearch:
        print("\n[4/5] Connecting to Elasticsearch...")
        try:
            es_cfg = storage_config.get("elasticsearch", {})
            
            config = ElasticsearchConfig(
                url=es_cfg.get("url", "http://localhost:9200"),
                index_name=es_cfg.get("index_name", "newbee_notebook_docs"),
            )
            
            es_index = await load_es_index(embed_model, config)
            print("Elasticsearch connected")
        except Exception as e:
            print(f"Warning: Could not connect to Elasticsearch: {e}")
            print("Ask mode will use pgvector only")
    else:
        print("\n[4/5] Skipping Elasticsearch (--no-elasticsearch)")
    
    # In CLI mode we use in-memory repositories
    session_repo = InMemorySessionRepo()
    message_repo = InMemoryMessageRepo()
    
    print("\n[5/5] Using in-memory session/message repositories for CLI mode")
    
    return llm, pgvector_index, es_index, session_repo, message_repo


async def main_async(args):
    """Async main function."""
    print_banner()
    
    try:
        # Initialize services
        llm, pgvector_index, es_index, session_repo, message_repo = await initialize_services(args)
        
        # Get ES index name from config
        storage_config = get_storage_config()
        es_index_name = storage_config.get("elasticsearch", {}).get("index_name", "newbee_notebook_docs")
        
        # Create session manager
        session_manager = SessionManager(
            llm=llm,
            session_repo=session_repo,
            message_repo=message_repo,
            pgvector_index=pgvector_index,
            es_index=es_index,
            es_index_name=es_index_name,
        )
        
        await session_manager.start_session(notebook_id="cli-notebook")
        print(f"[Session] Created new session: {session_manager.session_id}")
        
        # Set initial mode
        initial_mode = ModeType(args.mode) if args.mode else ModeType.CHAT
        session_manager.switch_mode(initial_mode)
        
        print("\n" + "=" * 60)
        print(f"Ready! Current mode: {initial_mode.value}")
        print("=" * 60)
        
        # Main conversation loop
        while True:
            try:
                user_input = input(f"\n[{session_manager.current_mode.value}] User: ").strip()
                
                # Handle empty input
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['/quit', '/exit', '/q', 'quit', 'exit']:
                    print("Assistant: Goodbye! Stay healthy!")
                    break
                
                if user_input.lower() == '/help':
                    print(get_mode_help())
                    continue
                
                if user_input.lower() == '/status':
                    print_status(session_manager)
                    continue

                if user_input.lower().startswith('/history'):
                    try:
                        parts = user_input.split()
                        limit = int(parts[1]) if len(parts) > 1 else 20
                    except Exception:
                        limit = 20
                    history = await session_manager.get_history(limit=limit)
                    print(f"\n--- Last {len(history)} messages ---")
                    for msg in history:
                        ts = ""
                        if hasattr(msg, "created_at") and msg.created_at:
                            try:
                                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                ts = str(msg.created_at)
                        mode_val = msg.mode.value if hasattr(msg.mode, "value") else str(getattr(msg, "mode", ""))
                        role_val = msg.role.value if hasattr(msg.role, "value") else str(getattr(msg, "role", ""))
                        print(f"[{ts}] ({mode_val}) {role_val}: {msg.content}")
                    print("----------------------")
                    continue

                if user_input.lower().startswith('/session list'):
                    if session_manager.session_store:
                        sessions = await session_manager.session_store.list_sessions(limit=20)
                        print("\n--- Recent Sessions ---")
                        for s in sessions:
                            print(f"{s.session_id} | created: {s.created_at} | updated: {s.updated_at}")
                        print("-----------------------")
                    else:
                        print("Session listing unavailable (no persistence configured).")
                    continue

                if user_input.lower().startswith('/resume'):
                    parts = user_input.split()
                    if len(parts) < 2:
                        print("Usage: /resume <session_id>")
                        continue
                    target = parts[1]
                    try:
                        await session_manager.end_session()
                        await session_manager.start_session(session_id=target)
                        print(f"Resumed session {target}")
                    except Exception as e:
                        print(f"Failed to resume session: {e}")
                    continue

                if user_input.lower().startswith('/delete'):
                    parts = user_input.split()
                    if len(parts) < 2:
                        print("Usage: /delete <session_id>")
                        continue
                    target = parts[1]
                    if session_manager.session_store:
                        try:
                            await session_manager.session_store.delete_session(target)
                            if session_manager.session_id == target:
                                await session_manager.end_session()
                            print(f"Deleted session {target}")
                        except Exception as e:
                            print(f"Failed to delete session: {e}")
                    else:
                        print("Delete unavailable (no persistence configured).")
                    continue
                
                if user_input.lower() == '/reset':
                    await session_manager.reset()
                    print("Assistant: Conversation memory has been reset.")
                    continue
                
                if user_input.lower() == '/new':
                    # Close current session and create a new one
                    old_session_id = session_manager.session_id
                    await session_manager.end_session()
                    await session_manager.start_session()
                    new_session_id = session_manager.session_id
                    print(f"\n[Session] Closed previous session: {old_session_id}")
                    print(f"[Session] Created new session: {new_session_id}")
                    print("Assistant: New conversation started. How can I help you today?")
                    continue
                
                # Handle mode switch
                parsed_mode, message = parse_mode_from_input(user_input)
                if parsed_mode:
                    session_manager.switch_mode(parsed_mode)
                    print(f"Assistant: Switched to {parsed_mode.value} mode.")
                    if not message:
                        continue
                    user_input = message
                
                # Get response
                response, sources = await session_manager.chat(user_input)
                print(f"\nAssistant: {response}")
                
            except KeyboardInterrupt:
                print("\n\nAssistant: Goodbye! Stay healthy!")
                break
            except EOFError:
                print("\n\nAssistant: Input stream ended. Goodbye!")
                break
            except Exception as e:
                print(f"\nAssistant: Sorry, an error occurred: {str(e)}")
                print("Please try rephrasing your question.")
        
        # Cleanup
        await session_manager.end_session()
        if session_manager.session_store:
            await session_manager.session_store.close()
    
    except ValueError as e:
        print(f"\nError: {e}")
        print("\nPlease ensure:")
        print("1. ZHIPU_API_KEY is set in your environment or .env file")
        print("2. Configuration files are properly set up in configs/")
        sys.exit(1)
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Newbee Notebook - Multi-Mode Medical Q&A Assistant",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["chat", "ask", "conclude", "explain"],
        default="chat",
        help="Initial interaction mode (default: chat)",
    )
    parser.add_argument(
        "--no-pgvector",
        action="store_true",
        help="Disable pgvector (RAG modes will not work)",
    )
    parser.add_argument(
        "--no-elasticsearch",
        action="store_true",
        help="Disable Elasticsearch (hybrid retrieval will not work)",
    )
    parser.add_argument(
        "--no-persistence",
        action="store_true",
        help="Disable session persistence",
    )
    
    args = parser.parse_args()
    
    # Run async main
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
