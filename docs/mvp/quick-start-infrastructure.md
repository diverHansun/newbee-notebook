# Quick Start: Infrastructure Setup

## Prerequisites
- Docker and Docker Compose installed
- Python 3.10+ with pip or uv
- ZhipuAI API Key
- Tavily API Key (optional, for Chat mode)

## Step 1: Install Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (faster)
uv pip install -r requirements.txt
```

## Step 2: Start Database Services

```bash
# Start PostgreSQL + Elasticsearch
docker-compose up -d

# Check services are running
docker-compose ps

# View logs
docker-compose logs -f
```

Expected output:
```
medimind-postgres         running   0.0.0.0:5432->5432/tcp
medimind-elasticsearch    running   0.0.0.0:9200->9200/tcp
```

## Step 3: Configure Environment

Create `.env` file in project root:

```bash
# ZhipuAI API Key (required)
ZHIPU_API_KEY=your_key_here

# PostgreSQL (default values match docker-compose)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medimind
POSTGRES_USER=postgres
POSTGRES_PASSWORD=medimind_password

# Elasticsearch (default values match docker-compose)
ELASTICSEARCH_URL=http://localhost:9200

# Tavily API Key (for Chat mode)
TAVILY_API_KEY=your_tavily_key_here
```

## Step 4: Verify Infrastructure

Run unit tests:

```bash
pytest tests/unit/test_infrastructure.py -v
```

Expected output:
```
tests/unit/test_infrastructure.py::TestPGVectorConfig::test_default_config PASSED
tests/unit/test_infrastructure.py::TestPGVectorConfig::test_connection_string PASSED
...
==================== X passed in X.XXs ====================
```

## Step 5: Initialize Database (When Ready)

Once modes are implemented, you can initialize:

```python
# This will be available in Phase 2+
from src.infrastructure import PGVectorStore, ChatSessionStore
from src.infrastructure.pgvector.config import PGVectorConfig
from src.common.config import get_storage_config

# Load configuration
storage_config = get_storage_config()
pg_config = PGVectorConfig(**storage_config['postgresql'])

# Initialize stores
pgvector_store = PGVectorStore(pg_config)
await pgvector_store.initialize()

session_store = ChatSessionStore(pg_config)
await session_store.initialize()

# Tables are created automatically
```

## Troubleshooting

### PostgreSQL Connection Failed
```bash
# Check if container is running
docker ps | grep postgres

# Check logs
docker logs medimind-postgres

# Restart container
docker-compose restart postgres
```

### Elasticsearch Connection Failed
```bash
# Check if container is running
docker ps | grep elasticsearch

# Test connection
curl http://localhost:9200

# Check logs
docker logs medimind-elasticsearch
```

### Port Already in Use
```bash
# Find process using port 5432 (PostgreSQL)
netstat -ano | findstr :5432

# Or port 9200 (Elasticsearch)
netstat -ano | findstr :9200

# Stop Docker services and restart
docker-compose down
docker-compose up -d
```

## Cleanup

Stop and remove all services:

```bash
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v
```

## Next Steps

After infrastructure is verified:
1. Continue to Phase 2: Tools Layer
2. Implement Tavily and ES search tools
3. Build hybrid retrieval system
4. Implement the four modes
