# Database Scripts

This directory contains database initialization and migration scripts.

## Directory Structure

```text
newbee_notebook/scripts/db/
|-- README.md
|-- init-postgres.sql
`-- migrations/
```

## Initialization Script

### `init-postgres.sql`

This script runs automatically when the PostgreSQL container starts for the first time.

What it does:
1. Enables `vector` extension for pgvector similarity search
2. Enables `uuid-ossp` extension for UUID generation
3. Enables `pgcrypto` extension for `gen_random_uuid()`
4. Creates core business tables (`library`, `notebooks`, `documents`, `sessions`, etc.)
5. Creates legacy chat tables (`chat_sessions`, `chat_messages`) for backward compatibility
6. Documents expected pgvector tables for active embedding providers:
   - `data_documents_qwen3_embedding` (1024 dims)
   - `data_documents_zhipu` (1024 dims)

Automatic execution:
- Mounted to `/docker-entrypoint-initdb.d/` in the container
- PostgreSQL automatically executes `.sql` files in this directory on first run

Manual execution:

```bash
docker exec -i newbee-notebook-postgres psql -U postgres -d newbee_notebook < newbee_notebook/scripts/db/init-postgres.sql
```

## Verifying Initialization

Check pgvector extension:

```bash
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

Check tables:

```bash
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "\dt"
```

Check indexes:

```bash
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "\di"
```

## Migration Strategy

For future schema changes:
1. Create numbered migration files, such as `001_add_column.sql`
2. Track applied migrations in a `schema_migrations` table
3. Use a migration tool or manual SQL execution

## Troubleshooting

If pgvector is not enabled after container start:

```bash
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Reset database (warning: deletes all data):

```bash
docker-compose down -v
docker-compose up -d
```
