# TicketFlow

TicketFlow is a production-minded support-ticket API built for the backend engineering assignment. It accepts and tracks customer tickets, enforces a ticket lifecycle, retains an append-only audit trail, and performs asynchronous deterministic triage through Celery and Redis.

The project is intentionally small enough to review quickly, while showing the engineering boundaries expected of a service that could evolve into a fintech support workflow.

## Project overview

### Capabilities

- Create a ticket with validated customer, subject, description, category, and priority data.
- Retrieve one ticket with its complete event history.
- List tickets with page-based pagination and optional status, priority, and category filters.
- Enforce valid lifecycle transitions: `OPEN`, `IN_PROGRESS`, `RESOLVED`, and `CLOSED`.
- Persist an immutable event for ticket creation, status changes, and automatic processing.
- Process new tickets asynchronously: route to a department, generate a deterministic summary, and record a bounded spam score.
- Expose liveness, database-readiness, Prometheus-format metrics, structured errors, request IDs, and JSON logs.

The worker is deliberately deterministic—not an LLM agent. It is the correct asynchronous integration point for future policy, ML, or LLM triage, without requiring external API credentials for this assignment.

## Architecture and design decisions

```text
                         ┌─────────────────────────────────┐
                         │            PostgreSQL           │
Client ──HTTP──> FastAPI │ tickets · identities · events    │
              │          │ outbox · dead letters            │
              │          └─────────────────────────────────┘
              │                          │
              └── creates ticket + event + outbox intent ───┘
                                         │
                              Celery relay task / Beat
                                         │
                                    Redis broker
                                         │
                                   Celery worker
                                         │
                         durable processing state + event
```

### Layering

The code is organised by responsibility, without introducing unnecessary framework layers:

```text
app/
├── core/              # Settings, domain errors, structured logging
├── models/            # SQLAlchemy entities and database-backed enums
│   ├── identity.py    # Actor, Customer, Agent
│   ├── tickets.py     # Ticket, TicketEvent, ticket lifecycle enums
│   └── processing.py  # OutboxMessage and DeadLetterMessage
├── services/          # Business use cases
│   ├── tickets.py     # Ticket creation, querying, lifecycle transitions
│   └── processing.py  # Worker lifecycle, idempotency, triage result
├── repositories.py    # Query and persistence access for ticket workflows
├── schemas.py         # Pydantic request/response DTOs
├── main.py            # HTTP routes, error mapping, observability endpoints
└── worker.py          # Celery tasks and transactional-outbox relay
migrations/            # Forward Alembic schema migrations
scripts/seed.py        # Idempotent local seed data
tests/                 # API, service, and PostgreSQL schema coverage
```

- **DTOs at the API boundary:** Pydantic schemas validate input and define stable response contracts. FastAPI generates OpenAPI from these schemas.
- **Service and repository separation:** routes remain thin; services own business rules and transaction boundaries; the repository owns query construction.
- **Configuration:** typed settings load from environment variables and fail fast for invalid environment, log level, database URL, or Redis URL.
- **Errors and logs:** expected failures use a consistent JSON error envelope. Each response carries `X-Request-ID`, which is also included in structured JSON request logs.
- **Lifecycle validation:** transition rules are explicit in the ticket service. A closed ticket is terminal.

### Data integrity and audit design

The database is designed to protect important invariants even if writes bypass the API:

- `actors` is the identity root, typed as `CUSTOMER`, `AGENT`, or `SYSTEM`.
- `customers` and `agents` are typed profiles over an actor. `tickets.customer_id` avoids copying customer names and emails onto every ticket.
- `ticket_events` references the typed actor identity with a composite foreign key. Database checks restrict which actor type and status fields are valid for each event kind.
- PostgreSQL enums protect ticket priority, category, status, actor type, processing state, and outbox state.
- Check constraints validate ticket text length, the 0–100 spam-score range, complete processing output, and event shape.
- Filter indexes support common list queries; `(ticket_id, created_at)` supports chronological event retrieval.
- A PostgreSQL trigger rejects `UPDATE` and `DELETE` on `ticket_events`, enforcing append-only audit history at the database layer.

### Reliable asynchronous processing

Ticket creation commits the ticket, its `CREATED` audit event, and an `outbox_messages` record in one transaction. A Celery relay publishes committed outbox messages to Redis; Celery Beat runs the relay every ten seconds as an eventual-delivery backstop.

The worker persists `PENDING`, `PROCESSING`, `COMPLETED`, or `FAILED` state, attempt count, task ID, timestamps, and safe error text on the ticket. Re-delivered tasks are skipped once processing is completed or already in progress. Celery retries failures up to three times with exponential backoff; a final failure is persisted to `dead_letter_messages` for investigation.

## Quick start with Docker Compose

### Prerequisites

- Docker Desktop (includes Docker Compose)
- Port `8000` available on your machine

Start the API, PostgreSQL, Redis, Celery worker, and Celery Beat:

```bash
docker compose up --build
```

When the logs show Uvicorn is running, open:

- API documentation: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Liveness: <http://localhost:8000/health>
- Readiness (checks PostgreSQL): <http://localhost:8000/ready>
- Metrics: <http://localhost:8000/metrics>

In another terminal, load one idempotent sample ticket:

```bash
docker compose exec api python scripts/seed.py
```

Run in the background with `docker compose up -d --build`, inspect logs with `docker compose logs -f api worker beat`, and stop services with:

```bash
docker compose down
```

`docker compose down` preserves the local PostgreSQL volume. Use `docker compose down -v` only when you intentionally want to delete local database data.

## Environment variables

Docker Compose provides local development defaults, so a `.env` file is optional. To override them, copy the template and edit it:

```bash
cp .env.example .env
```

| Variable | Compose default | Purpose |
|---|---|---|
| `APP_NAME` | `TicketFlow API` | Application name used in generated API documentation. |
| `ENVIRONMENT` | `development` | One of `development`, `test`, `staging`, or `production`. |
| `DATABASE_URL` | `postgresql+psycopg://ticketflow:ticketflow@db:5432/ticketflow` | SQLAlchemy PostgreSQL connection URL. |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker and result-backend URL. |
| `LOG_LEVEL` | `INFO` | Python logging level, for example `DEBUG` or `WARNING`. |
| `AUTO_PROCESS_TICKETS` | `true` | Whether ticket creation immediately asks Celery to relay the outbox; Beat still relays pending intents. |

The Compose database password is intentionally a local-only convenience. Do not use it outside local development; inject production secrets through a managed secret store.

## API guide

Interactive documentation at `/docs` is the source of truth for request and response schemas. The primary endpoints are:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe. |
| `GET` | `/ready` | Readiness probe; verifies database connectivity. |
| `GET` | `/metrics` | Prometheus-format application metrics. |
| `POST` | `/v1/tickets` | Create a ticket, audit event, and processing intent. |
| `GET` | `/v1/tickets/{ticket_id}` | Fetch a ticket and its event history. |
| `GET` | `/v1/tickets` | List tickets; accepts `page`, `page_size`, `status`, `priority`, and `category`. |
| `PATCH` | `/v1/tickets/{ticket_id}/status` | Apply a validated status transition as an agent. |

Create a ticket:

```bash
curl -X POST http://localhost:8000/v1/tickets \
  -H 'content-type: application/json' \
  -d '{
    "customer_name": "Ava Sharma",
    "customer_email": "ava@example.com",
    "subject": "Card payment pending",
    "description": "My card payment has been pending for more than 24 hours.",
    "priority": "HIGH",
    "category": "PAYMENT"
  }'
```

Move ticket `1` into progress:

```bash
curl -X PATCH http://localhost:8000/v1/tickets/1/status \
  -H 'content-type: application/json' \
  -d '{"status":"IN_PROGRESS","actor":"agent:ava"}'
```

Allowed transitions are:

```text
OPEN        -> IN_PROGRESS, CLOSED
IN_PROGRESS -> RESOLVED, CLOSED
RESOLVED    -> IN_PROGRESS, CLOSED
CLOSED      -> (terminal)
```

Errors have one predictable shape and carry the request ID needed to find the corresponding log entry:

```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "request_id": "...",
  "details": [{"location": ["body", "subject"], "message": "Field required", "type": "missing"}]
}
```

## Running without Docker

Use Python 3.12+ and provide reachable PostgreSQL and Redis instances. The default URLs in application settings target `localhost`; set `DATABASE_URL` and `REDIS_URL` if yours differ.

```bash
python -m venv .venv
. .venv/bin/activate
pip install --requirement requirements-dev.lock
pip install --no-deps -e .
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
```

In separate terminals (with the same virtual environment and configuration), start the worker and scheduled outbox relay:

```bash
celery -A app.worker.celery_app worker --loglevel=INFO
celery -A app.worker.celery_app beat --loglevel=INFO
```

## Database migrations and tests

Migrations are forward Alembic revisions in `migrations/versions/`; apply them with `alembic upgrade head`. The seed script is safe to rerun: it skips insertion once tickets exist.

Run static checks and tests:

```bash
ruff check app tests migrations scripts
pytest
```

The test suite covers API response contracts, validation errors, filtering and pagination, status transitions, asynchronous-processing idempotency, and PostgreSQL-specific schema guarantees. Set `POSTGRES_INTEGRATION_URL` to run the PostgreSQL schema test locally; the GitHub Actions pipeline supplies it automatically, applies migrations, runs Ruff and pytest, and performs a Docker Compose smoke test.

## Tradeoffs and assumptions

- **No authentication or authorization:** this is assignment scope. In production, authentication would resolve the caller to a customer or agent identity, enforce tenant isolation, and remove the client-controlled `actor` field from status updates.
- **Deterministic triage, not AI:** routing and spam scoring are deliberately explainable stubs. A real model integration should include prompt/model versioning, PII controls, evaluation, fallbacks, cost limits, and human review.
- **At-least-once delivery:** the transactional outbox makes the database intent durable and the worker is designed to safely skip completed/in-progress work. A broker publish can still be retried, so processing remains deliberately idempotent rather than assuming exactly-once delivery.
- **Dead-letter persistence, not a managed DLQ:** terminal worker failures are stored in PostgreSQL for inspection. A larger deployment could additionally route them to a broker-native DLQ and alerting workflow.
- **Metrics endpoint, not full observability platform:** `/metrics` is scrape-ready and request logs include correlation IDs. Production would add a Prometheus/Grafana deployment, distributed tracing, dashboards, SLOs, and alerting.
- **Single-service, synchronous REST API:** pagination is offset-based and suitable for assignment-scale data. High-volume feeds would use cursor pagination, rate limits, request-size limits, idempotency keys, and stronger query budgets.
- **Migration ownership:** the append-only trigger protects normal SQL writes; privileged database operators can still alter schema or permissions. Production audit requirements may call for restricted database roles or a dedicated audit store.

## Continuous integration

Every push and pull request runs GitHub Actions. The test job starts PostgreSQL, applies migrations, runs Ruff, and executes pytest (including PostgreSQL-only checks). A separate job builds the Compose stack and verifies `/health`, `/ready`, and ticket creation end to end.
