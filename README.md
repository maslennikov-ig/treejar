# Treejar AI Sales Bot

AI-powered sales assistant for **Treejar** office furniture company. Communicates with customers via WhatsApp (Wazzup gateway), consults on products, checks stock and pricing, creates quotations (Zoho Inventory), and manages CRM records (Zoho CRM).

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.13, FastAPI |
| Database | Self-hosted PostgreSQL 16 + pgvector (Hetzner) |
| Cache/Queue | Redis 8.0 + ARQ |
| AI Orchestration | PydanticAI, OpenRouter |
| WhatsApp | Wazzup API |
| CRM | Zoho CRM + Zoho Inventory (custom httpx) |
| Admin | SQLAdmin |
| Embeddings | BAAI/bge-m3 via FastEmbed |

## Quick Start

```bash
# Clone and configure
git clone <repo-url> && cd treejar
cp .env.example .env
# Edit .env with your credentials

# Start services
docker compose up -d                    # Production (self-hosted PostgreSQL on Hetzner)
docker compose -f docker-compose.yml \
  -f docker-compose.dev.yml up -d       # Local dev (local PostgreSQL via Docker)

# Run migrations
alembic upgrade head

# Verify
curl http://localhost:8000/api/v1/health
```

- Swagger UI: http://localhost:8000/docs
- Admin panel: http://localhost:8000/admin/

## Development

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run
uvicorn src.main:app --reload --port 8000

# Quality
ruff check src/ tests/
mypy src/
pytest tests/ -v
```

## Project Structure

```
src/
  api/v1/          # FastAPI routes (25 endpoints)
  core/            # Config, database, redis, security
  models/          # SQLAlchemy models (6 tables)
  schemas/         # Pydantic schemas (API contracts)
  llm/             # LLM engine + prompt templates
  rag/             # RAG pipeline (SQL + pgvector)
  integrations/    # Wazzup, Zoho CRM, Zoho Inventory
  quality/         # Conversation quality evaluator
migrations/        # Alembic migrations
tests/             # pytest test suite
docs/              # Project documentation
```

## Documentation

- [Technical Specification](docs/tz.md)
- [Architecture](docs/architecture.md)
- [Development Guide](docs/dev-guide.md)
- [Roadmap](docs/roadmap.md)
