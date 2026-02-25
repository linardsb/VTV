.PHONY: dev dev-be dev-fe docker docker-down docker-prod docker-prod-down test lint types check db db-backup db-backup-auto db-restore e2e e2e-all e2e-ui e2e-headed install-hooks security-check security-audit-quick security-audit security-audit-full dep-audit

# === Local Development (terminals) ===

dev: ## Start db + backend + frontend with health checks (full local dev)
	@bash scripts/dev.sh

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

e2e: ## Run e2e tests for changed features only (or all if nothing detected)
	@TESTS=$$(cd cms/apps/web && ./e2e/detect-changed.sh); \
	if [ -z "$$TESTS" ]; then \
		echo "No frontend changes detected — running full suite"; \
		cd cms && pnpm --filter @vtv/web e2e; \
	else \
		echo "Changed features detected — running: $$TESTS"; \
		cd cms/apps/web && npx playwright test $$TESTS; \
	fi

e2e-all: ## Run ALL e2e tests regardless of changes
	cd cms && pnpm --filter @vtv/web e2e

e2e-ui: ## Open Playwright UI mode for interactive testing
	cd cms && pnpm --filter @vtv/web e2e:ui

e2e-headed: ## Run e2e tests with visible browser
	cd cms && pnpm --filter @vtv/web e2e:headed

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

db-backup-auto: ## Automated backup with 90-day retention (cron-ready)
	./scripts/db-backup.sh 90

db-restore: ## Restore from backup (usage: make db-restore f=backups/file.sql.gz)
	@test -n "$(f)" || (echo "Usage: make db-restore f=backups/file.sql.gz" && exit 1)
	@test -f "$(f)" || (echo "ERROR: File $(f) not found" && exit 1)
	gunzip -c "$(f)" | docker exec -i vtv-db-1 psql -U postgres vtv_db

# === Security ===

install-hooks: ## Install git pre-commit hook
	cp scripts/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed."

security-check: ## Run security lint (Ruff Bandit rules)
	uv run ruff check app/ --select=S --no-fix

security-audit-quick: ## Security audit (quick - pre-commit equivalent, <10s)
	./scripts/security-audit.sh --level quick

security-audit: ## Security audit (standard - CI equivalent, ~60s)
	./scripts/security-audit.sh --level standard

security-audit-full: ## Security audit (full - all checks including container + nginx, ~120s)
	./scripts/security-audit.sh --level full

dep-audit: ## Scan dependencies for known vulnerabilities
	uv run pip-audit --desc --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2024-23342

# === Help ===

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
