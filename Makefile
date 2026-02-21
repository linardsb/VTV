.PHONY: dev dev-be dev-fe docker docker-down test lint types check db

# === Local Development (terminals) ===

dev: db ## Start db + backend + frontend (full local dev)
	@trap 'kill 0' EXIT; \
	uv run uvicorn app.main:app --reload --port 8123 & \
	(cd cms && pnpm --filter @vtv/web dev) & \
	wait

dev-be: ## Start backend dev server
	uv run uvicorn app.main:app --reload --port 8123

dev-fe: ## Start frontend dev server
	cd cms && pnpm --filter @vtv/web dev

# === Docker (integration / pre-deployment) ===

docker: ## Build and start all services (db, redis, auto-migrate, app, cms, nginx on :80)
	AUTH_SECRET=$$(openssl rand -base64 32) docker-compose up -d --build

docker-down: ## Stop all Docker services
	docker-compose down

docker-logs: ## Tail logs from all services
	docker-compose logs -f

# === Quality Checks ===

test: ## Run unit tests
	uv run pytest -v -m "not integration"

lint: ## Format + lint
	uv run ruff format .
	uv run ruff check --fix .

types: ## Run mypy + pyright
	uv run mypy app/
	uv run pyright app/

check: lint types test ## Run all checks (lint, types, tests)

# === Database ===

db: ## Start only PostgreSQL + Redis (for local dev)
	AUTH_SECRET=dev-placeholder docker-compose up -d db redis

db-migrate: ## Run database migrations
	uv run alembic upgrade head

db-revision: ## Create a new migration (usage: make db-revision m="description")
	uv run alembic revision --autogenerate -m "$(m)"

# === Help ===

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
