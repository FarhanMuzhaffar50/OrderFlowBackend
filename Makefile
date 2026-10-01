.DEFAULT_GOAL := help

.PHONY: help install run lint format typecheck test test-unit test-integration migrate revision seed compose-up compose-down compose-logs build

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install the project with development dependencies
	python -m pip install --upgrade pip
	python -m pip install -e '.[dev]'

run: ## Run the API locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint: ## Run Ruff checks
	ruff check .

format: ## Format with Ruff
	ruff format .

typecheck: ## Run static type checks
	mypy src

test: ## Run the full test suite
	pytest

test-unit: ## Run unit tests only
	pytest -m "not integration"

test-integration: ## Run integration tests (requires PostgreSQL and Redis)
	pytest -m integration

migrate: ## Apply Alembic migrations
	alembic upgrade head

revision: ## Create an Alembic revision; message="describe change"
	alembic revision --autogenerate -m "$(message)"

seed: ## Seed local demo data
	python -m app.scripts.seed

compose-up: ## Start local services in the background
	docker compose up --build -d

compose-down: ## Stop local services (preserves volumes)
	docker compose down

compose-logs: ## Stream local service logs
	docker compose logs --follow

build: ## Build the API image
	docker build --tag orderflow:local .
