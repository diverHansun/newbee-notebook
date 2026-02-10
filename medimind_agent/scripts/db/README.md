# Database Scripts

This directory contains database initialization and migration scripts.

## Directory Structure

```
medimind_agent/scripts/db/
├── README.md              # This file
├── init-postgres.sql      # PostgreSQL initialization (runs on first start)
└── migrations/            # Future migration scripts (if needed)
```

## Initialization Script

### init-postgres.sql

This script runs automatically when the PostgreSQL container starts for the first time.

**What it does:**
1. Enables `vector` extension for pgvector similarity search
2. Enables `uuid-ossp` extension for UUID generation
3. Creates `chat_sessions` table for conversation management
4. Creates `chat_messages` table for message storage
5. Creates indexes for optimal query performance

**Automatic execution:**
- Mounted to `/docker-entrypoint-initdb.d/` in the container
- PostgreSQL automatically executes `.sql` files in this directory on first run

**Manual execution (if needed):**
```bash
docker exec -i medimind-postgres psql -U postgres -d medimind < medimind_agent/scripts/db/init-postgres.sql
```

## Verifying Initialization

### Check pgvector extension:
```bash
docker exec medimind-postgres psql -U postgres -d medimind -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### Check tables:
```bash
docker exec medimind-postgres psql -U postgres -d medimind -c "\dt"
```

### Check indexes:
```bash
docker exec medimind-postgres psql -U postgres -d medimind -c "\di"
```

## Migration Strategy

For future schema changes:

1. Create numbered migration files: `001_add_column.sql`, `002_create_table.sql`
2. Track applied migrations in a `schema_migrations` table
3. Use a migration tool or manual SQL execution

## Troubleshooting

### Extension not enabled:
If pgvector is not enabled after container start:
```bash
docker exec medimind-postgres psql -U postgres -d medimind -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Reset database:
To completely reset the database (WARNING: deletes all data):
```bash
docker-compose down -v
docker-compose up -d
```
