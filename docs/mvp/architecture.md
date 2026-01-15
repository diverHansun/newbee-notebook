# MediMind Agent Architecture

## Overview

MediMind Agent is a multi-mode medical Q&A assistant built with LlamaIndex framework.

## Directory Structure

```
src/
├── common/              # Shared configuration
│   ├── __init__.py
│   └── config.py        # YAML config loading + env overrides
│
├── engine/              # Core Engine Layer
│   ├── __init__.py      # Module exports
│   ├── modes/           # Interaction modes
│   │   ├── base.py      # BaseMode, ModeType, ModeConfig
│   │   ├── chat_mode.py # FunctionAgent + tools
│   │   ├── ask_mode.py  # ReActAgent + hybrid RAG
│   │   ├── conclude_mode.py  # ChatEngine + RAG
│   │   └── explain_mode.py   # QueryEngine + RAG
│   ├── selector.py      # ModeSelector factory
│   ├── session.py       # SessionManager
│   └── index_builder.py # Index building utilities
│
├── infrastructure/      # Infrastructure Layer
│   ├── __init__.py
│   ├── pgvector/        # PostgreSQL + pgvector
│   │   ├── config.py    # PGVectorConfig
│   │   └── store.py     # PGVectorStore wrapper
│   ├── elasticsearch/   # Elasticsearch
│   │   ├── config.py    # ElasticsearchConfig
│   │   └── store.py     # ElasticsearchStore wrapper
│   └── session/         # Session persistence
│       ├── models.py    # ChatSession, ChatMessage
│       └── store.py     # ChatSessionStore
│
├── llm/                 # LLM Layer
│   ├── __init__.py
│   └── zhipu.py         # ZhipuAI LLM builder
│
├── memory/              # Memory Layer
│   ├── __init__.py
│   └── chat_memory.py   # Conversation memory
│
├── rag/                 # RAG Components Layer
│   ├── __init__.py
│   ├── embeddings/      # Embedding models
│   │   ├── base.py      # Base embedding class
│   │   └── zhipu.py     # ZhipuAI embedding
│   ├── document_loader/ # Document loading
│   │   └── loader.py    # Multi-format loader
│   ├── text_splitter/   # Text chunking
│   │   └── splitter.py  # Sentence splitter
│   ├── retrieval/       # Retrieval strategies
│   │   ├── fusion.py    # RRF, weighted fusion
│   │   └── hybrid_retriever.py  # Hybrid retrieval
│   ├── generation/      # Response generation
│   │   ├── chat_engine.py   # ChatEngine builder
│   │   └── query_engine.py  # QueryEngine builder
│   └── postprocessors/  # Node postprocessing
│       └── processors.py
│
├── tools/               # Agent Tools Layer
│   ├── __init__.py
│   ├── tavily_tool.py   # Web search tool
│   └── es_search_tool.py # Knowledge base search tool
│
└── agent/               # Legacy Agent (deprecated)
    └── agent.py
```

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│                      (main.py CLI)                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│              (SessionManager, ModeSelector)                 │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Domain Layer                           │
│    (ChatMode, AskMode, ConcludeMode, ExplainMode)          │
└─────────────────────────────┬───────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│    RAG Layer    │ │   Tools Layer   │ │   LLM Layer     │
│  (Embeddings,   │ │ (Tavily, ES)    │ │  (ZhipuAI)      │
│   Retrieval)    │ │                 │ │                 │
└────────┬────────┘ └────────┬────────┘ └─────────────────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│        (pgvector, Elasticsearch, PostgreSQL)               │
└─────────────────────────────────────────────────────────────┘
```

## Four Interaction Modes

| Mode | Engine/Agent | Memory | RAG | Use Case |
|------|-------------|--------|-----|----------|
| **Chat** | FunctionAgent | Yes | Optional | General conversation |
| **Ask** | ReActAgent | Yes | Hybrid | Deep Q&A |
| **Conclude** | ChatEngine | No | pgvector | Summarization |
| **Explain** | QueryEngine | No | pgvector | Explanation |

## Data Flow

### Chat Mode
```
User → FunctionAgent → [Tavily/ES tools] → Response
                ↓
         Conversation Memory
```

### Ask Mode
```
User → ReActAgent → HybridRetriever → Response
           ↓              ↓
    Think-Act-Observe   pgvector + ES BM25
           ↓              ↓
    Conversation      RRF Fusion
       Memory
```

### Conclude/Explain Modes
```
User → ChatEngine/QueryEngine → pgvector → Response
                                    ↓
                              Document Retrieval
```

## Key Design Patterns

1. **Template Method Pattern** - BaseMode defines algorithm skeleton
2. **Strategy Pattern** - FusionStrategy for result merging
3. **Factory Pattern** - ModeSelector creates modes
4. **Repository Pattern** - Store classes abstract data access
5. **Dependency Inversion** - Modes depend on abstractions

## Configuration Files

```
configs/
├── llm.yaml        # LLM settings
├── embeddings.yaml # Embedding model settings
├── memory.yaml     # Memory configuration
├── storage.yaml    # Database connections
├── modes.yaml      # Mode definitions
└── rag.yaml        # RAG pipeline settings
```

## Environment Variables

See `.env.example` for all available settings:
- `ZHIPU_API_KEY` - LLM API key (required)
- `TAVILY_API_KEY` - Web search API key (optional)
- `POSTGRES_*` - PostgreSQL connection
- `ELASTICSEARCH_URL` - Elasticsearch connection
