# Verification record

Verified on 2026-10-01 in the local development environment (macOS host, Python 3.13 test runner, Python 3.12 container runtime, PostgreSQL 16, Redis 7).

| Area | Command / evidence | Result |
|---|---|---|
| Repository inspection | `rg --files` and targeted source review | PASS |
| Formatting | `ruff format --check .` | PASS — 54 files formatted |
| Lint | `ruff check .` | PASS |
| Type checking | `mypy src mock_payment_provider` | PASS — 32 source files |
| Complete tests | `pytest -q` with PostgreSQL/Redis environment | PASS — 20 tests |
| PostgreSQL concurrency | `tests/integration/test_checkout_concurrency.py` in complete suite | PASS — two simultaneous buyers, one unit, exactly one success |
| Checkout idempotency | `tests/integration/test_checkout_idempotency.py` | PASS |
| Payment/webhook idempotency | payment and API integration tests | PASS |
| Migrations | `alembic upgrade head` | PASS — revision `0001` applied |
| Seed data | `docker compose exec -T api python -m app.scripts.seed` | PASS |
| Docker image | `docker build -t orderflow:local .` | PASS |
| Compose validation | `docker compose config -q` | PASS |
| Complete stack | `docker compose up -d --build` | PASS — all five services healthy |
| Live endpoints | `/health`, `/ready`, `/metrics`, provider `/health` | PASS |
| Worker scheduling | repeated `publish_outbox` Celery Beat executions | PASS |

The test runner emits one third-party `StarletteDeprecationWarning` from FastAPI's compatibility import; it does not affect application behavior or test results.
