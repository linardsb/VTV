.PHONY: dev dev-be dev-fe docker docker-down docker-prod docker-prod-down test lint types check db db-backup db-restore

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

# === Docker — Local Dev ===

docker: ## Build and start all services (local dev, port :80)
	@docker volume create vtv_postgres_data 2>/dev/null || true
	AUTH_SECRET=$$(openssl rand -base64 32) docker-compose up -d --build

docker-down: ## Stop all Docker services
	docker-compose down

docker-logs: ## Tail logs from all services
	docker-compose logs -f

# === Docker — Production ===

docker-prod: ## Production: build and start (requires .env.production)
	@docker volume create vtv_postgres_data 2>/dev/null || true
	@test -f .env.production || (echo "ERROR: .env.production not found. Copy from .env.production.example" && exit 1)
	docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml up -d --build

docker-prod-down: ## Production: stop all services
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

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
	@docker volume create vtv_postgres_data 2>/dev/null || true
	AUTH_SECRET=dev-placeholder docker-compose up -d db redis

db-migrate: ## Run database migrations
	uv run alembic upgrade head

db-revision: ## Create a new migration (usage: make db-revision m="description")
	uv run alembic revision --autogenerate -m "$(m)"

db-backup: ## Backup PostgreSQL to timestamped file
	@mkdir -p backups
	docker exec vtv-db-1 pg_dump -U postgres vtv_db | gzip > backups/vtv_db_$$(date +%Y%m%d_%H%M%S).sql.gz
	@ls -lh backups/vtv_db_*.sql.gz | tail -1

db-restore: ## Restore from backup (usage: make db-restore f=backups/file.sql.gz)
	@test -n "$(f)" || (echo "Usage: make db-restore f=backups/file.sql.gz" && exit 1)
	@test -f "$(f)" || (echo "ERROR: File $(f) not found" && exit 1)
	gunzip -c "$(f)" | docker exec -i vtv-db-1 psql -U postgres vtv_db

# === Help ===

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
