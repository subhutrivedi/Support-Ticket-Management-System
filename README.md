# TicketFlow

A production-style support ticket API designed for a fintech operating model: tickets are auditable, status changes are constrained, and new tickets are enriched asynchronously by a worker.

## What is included

- FastAPI REST API with OpenAPI documentation at `/docs` and `/openapi.json`
- PostgreSQL relational model: `tickets` plus immutable-style `ticket_events` audit history
- Enum-backed priority, category, and lifecycle statuses
- Pagination and filters for status, priority, and category
- Service/repository separation, typed Pydantic DTOs, request validation, structured error envelope, request IDs, JSON logging, and readiness checks
- Celery + Redis worker that routes tickets, calculates a deterministic spam score, and saves a summary
- Alembic migration, seed script, Docker Compose, and unit tests

## Architecture

```text
Client -> FastAPI API -> TicketService -> TicketRepository -> PostgreSQL
                  |                                  |
                  +-> Celery task -> Redis -> Worker -+
```

The API persists the ticket and its `CREATED` event in one database transaction before enqueueing. In a larger system, this handoff should use an outbox table and relay process to guarantee delivery across the database/broker boundary; that tradeoff keeps this assignment implementation compact while making the production direction explicit.

### Ticket lifecycle

`OPEN -> IN_PROGRESS -> RESOLVED -> CLOSED`, with `OPEN -> CLOSED` and `RESOLVED -> IN_PROGRESS` also permitted. A closed ticket is terminal. Every accepted state change writes a `STATUS_CHANGED` event.

### Data model choices

`tickets` is the current operational projection. `ticket_events` holds the time-ordered audit trail and has a compound index on `(ticket_id, created_at)`. Ticket list filters use compound indexes paired with `created_at` for common operational queries. Database enums prevent invalid category, priority, and status values. Check constraints enforce meaningful ticket fields, a bounded `spam_score`, complete async-enrichment output, and the valid shape of each audit event—even for direct database writes.

## Quick start

Prerequisites: Docker Desktop and Docker Compose.

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.
Compose has secure-for-local-development defaults, so no configuration file is required to start. Copy `.env.example` to `.env` only when you want to override them.

In another terminal, add example data:

```bash
docker compose exec api python scripts/seed.py
```

Stop services with `docker compose down`. Add `-v` only when you intentionally want to remove local PostgreSQL data.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/ready` | Readiness check (verifies database connectivity) |
| `POST` | `/v1/tickets` | Create a ticket and enqueue background enrichment |
| `GET` | `/v1/tickets/{id}` | Retrieve ticket plus event history |
| `GET` | `/v1/tickets?page=1&page_size=20&status=OPEN&priority=HIGH&category=PAYMENT` | Paginated, filterable list |
| `PATCH` | `/v1/tickets/{id}/status` | Make a validated agent status transition |

Create a ticket:

```bash
curl -X POST http://localhost:8000/v1/tickets \
  -H 'content-type: application/json' \
  -d '{"customer_name":"Ava Sharma","customer_email":"ava@gmail.com","subject":"Card payment pending","description":"My card payment has been pending for more than 24 hours.","priority":"HIGH","category":"PAYMENT"}'
```

Move it into progress:

```bash
curl -X PATCH http://localhost:8000/v1/tickets/1/status \
  -H 'content-type: application/json' \
  -d '{"status":"IN_PROGRESS","actor":"agent:ava"}'
```

Error responses consistently include a machine-readable error code, a safe message, validation details where relevant, and a request ID. The same ID is returned in `X-Request-ID` and included in JSON logs.

```json
{"error":"validation_error","message":"Request validation failed","request_id":"...","details":[{"location":["body","subject"],"message":"Field required","type":"missing"}]}
```

## Configuration

| Variable | Default / expected value | Purpose |
|---|---|---|
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL | API and worker database connection |
| `REDIS_URL` | `redis://redis:6379/0` in Compose | Celery broker and result backend |
| `AUTO_PROCESS_TICKETS` | `true` | Enqueue enrichment after creation |
| `LOG_LEVEL` | `INFO` | Application log verbosity |
| `ENVIRONMENT` | `development` | Environment label in startup logs |

Configuration is validated at startup: `ENVIRONMENT` must be `development`, `test`, `staging`, or `production`; `LOG_LEVEL` must be a Python logging level; database and Redis URLs must use supported schemes. Logs are emitted as JSON to standard output with timestamps, request IDs, route, status code, and duration.

## Local development

With Python 3.12 and a running PostgreSQL/Redis instance:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
celery -A app.worker.celery_app worker --loglevel=INFO
pytest
ruff check .
```

## Production considerations

- Authentication/authorization is intentionally out of assignment scope; production should add customer and agent identities plus tenant scoping.
- Use an outbox pattern, idempotency key, dead-letter queue, metrics/tracing, secrets manager, and managed PostgreSQL/Redis in deployment.
- The worker task is retryable and persists its result; routing and spam scoring are deterministic stubs ready to be replaced with policy or ML integrations.
- Keep database migrations forward-only in deployed environments and run them as an explicit release step.
