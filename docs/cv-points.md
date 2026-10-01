# CV points

## Project title

OrderFlow — Transaction-Safe Ordering System Backend

## One-line description

Built a production-style FastAPI modular monolith for authenticated catalog, inventory, checkout, and idempotent asynchronous payment workflows.

## Three primary bullets

- Designed PostgreSQL transaction boundaries and row-level inventory locking so concurrent checkout requests cannot oversell stock.
- Implemented idempotent checkout, provider charge retries, signed webhook handling, and transactional outbox events for reliable payment state transitions.
- Built a containerized backend with Redis cache-aside/rate limiting, background workers, structured observability, and automated test/CI support.

## Optional alternatives

- Modelled an explicit order state machine with guarded transitions, immutable order-item price snapshots, and database-backed monetary values in minor units.
- Separated API concerns from transaction-sensitive checkout and payment services in a modular monolith to keep domain logic testable and transactions understandable.
- Added deterministic mock-provider success, decline, and retryable-failure scenarios to exercise ambiguous external-dependency behavior.
- Added health/readiness endpoints, request correlation IDs, Prometheus-compatible metrics, and structured error responses for operational diagnosis.
- Documented an AWS production mapping from containers and ECR through ECS/Fargate, RDS, ElastiCache, ALB, Secrets Manager, and CloudWatch.

## Technology line

Python 3.12+, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Alembic, Redis, Celery/worker runtime, Docker Compose, pytest, Ruff, GitHub Actions.

Use only bullets whose corresponding implementation and verification status are confirmed in this repository. Do not add throughput, latency, uptime, user counts, or live-deployment claims without measured evidence.
