.PHONY: bootstrap dev dev-be dev-fe docker docker-down docker-prod docker-prod-down test lint types check db db-backup db-backup-auto db-restore e2e e2e-all e2e-ui e2e-headed install-hooks security-check security-audit-quick security-audit security-audit-full dep-audit deploy deploy-quick rechunk rechunk-dry-run download-udpipe-model lemmatize-backfill lemmatize-backfill-dry-run weather-backfill traffic-backfill er-diagram gtfs-backfill seed-schema-examples ml-train-eta ml-train-load

# === Local Development (terminals) ===

dev: ## Start db + backend + frontend with health checks (full local dev)
	@bash scripts/dev.sh

dev-be: ## Start backend dev server
	uv run uvicorn app.main:app --reload --port 8123

dev-fe: ## Start frontend dev server
	cd cms && pnpm --filter @vtv/web dev

bootstrap: ## First-time setup: install deps + pre-commit hooks
	uv sync --all-extras
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "Bootstrap complete. Pre-commit hooks installed."

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

rechunk: ## Re-chunk all documents with the new SemanticChunker (one-shot AI-4.4 migration)
	uv run python scripts/rechunk_documents.py

rechunk-dry-run: ## Preview re-chunking without modifying the database
	uv run python scripts/rechunk_documents.py --dry-run

download-udpipe-model: ## Fetch the Latvian UDPipe 2.5 model (KB-2, ~50MB)
	bash scripts/download_udpipe_model.sh

lemmatize-backfill: ## Backfill lemmatized_content on chunks of Latvian docs (KB-2)
	uv run python scripts/backfill_lemmatized_content.py

lemmatize-backfill-dry-run: ## Preview lemmatization backfill without writes (KB-2)
	uv run python scripts/backfill_lemmatized_content.py --dry-run

eticket-backfill: ## Backfill single month (usage: make eticket-backfill MONTH=2026-01)
	@test -n "$(MONTH)" || (echo "Usage: make eticket-backfill MONTH=2026-01" && exit 1)
	uv run python scripts/backfill_eticket_data.py --month $(MONTH)

eticket-backfill-all: ## Backfill ALL months (~45GB, alert ops first)
	uv run python scripts/backfill_eticket_data.py --all

eticket-backfill-dry-run: ## Preview e-ticket backfill without importing
	uv run python scripts/backfill_eticket_data.py --dry-run $(if $(MONTH),--month $(MONTH),--all)

weather-backfill: ## Backfill weather observations from archive (ML-1.3)
	uv run python scripts/weather_backfill.py

traffic-backfill: ## Backfill traffic counts and accidents (ML-1.3)
	uv run python scripts/traffic_backfill.py

er-diagram: ## Generate Mermaid ER diagram from SQLAlchemy models
	@mkdir -p docs/schema
	uv run python scripts/generate_er_diagram.py > docs/schema/er.md
	@echo "ER diagram written to docs/schema/er.md"

gtfs-backfill: ## Backfill historical GTFS snapshots from data.gov.lv
	uv run python scripts/backfill_gtfs_history.py --since $(or $(SINCE),2018-05) $(if $(UNTIL),--until $(UNTIL)) $(if $(DRY_RUN),--dry-run)

seed-schema-examples: ## Seed schema_examples table from YAML (ML-5.4)
	uv run python scripts/seed_schema_examples.py --file data/schema_examples.yaml

ml-train-eta: ## Train ETA model (usage: make ml-train-eta WINDOW=60)
	uv run python scripts/train_eta_model.py --training-window $(or $(WINDOW),60) --target-mae $(or $(TARGET_MAE),120)

ml-train-load: ## Train load prediction model (usage: make ml-train-load WINDOW=60)
	uv run python scripts/train_load_model.py --training-window $(or $(WINDOW),60) --target-mae $(or $(TARGET_MAE),12) --target-f1 $(or $(TARGET_F1),0.75)

# === Agent evals (AI-7.x) ===
# Traces are written to evals/traces/*.jsonl (git-ignored, may contain PII).

eval: ## Run eval suite (usage: make eval SUITE=transit|knowledge|vault|all)
	uv run python -m app.core.agents.evals.runner --suite $(or $(SUITE),transit)

eval-all: ## Run all three eval suites sequentially
	uv run python -m app.core.agents.evals.runner --suite all

eval-judge: ## Judge latest traces (usage: make eval-judge SUITE=transit|knowledge|vault|all)
	uv run python -m app.core.agents.evals.judge --suite $(or $(SUITE),transit)

eval-baseline: ## Generate or update baselines from latest judged run
	uv run python -m app.core.agents.evals.regression baseline --suite $(or $(SUITE),transit)

eval-check: ## Judge latest traces and compare against baseline (CI-friendly)
	uv run python -m app.core.agents.evals.regression check --suite $(or $(SUITE),transit)

# === RAG retrieval evals (AI-11.x) ===

rag-eval-generate: ## Generate synthetic QA pairs from knowledge base (usage: make rag-eval-generate COUNT=100)
	uv run python -m app.knowledge.evals --count $(or $(COUNT),100)

rag-eval-run: ## Run RAG eval on existing QA pairs (usage: make rag-eval-run QA_FILE=evals/rag/qa_pairs.jsonl)
	uv run python -m app.knowledge.evals.runner --qa-file $(or $(QA_FILE),evals/rag/qa_pairs.jsonl)

rag-eval: rag-eval-generate rag-eval-run ## Generate QA pairs + run RAG eval (usage: make rag-eval COUNT=100)

rag-eval-update-baseline: ## Update RAG eval baseline from latest report (usage: make rag-eval-update-baseline REPORT=evals/rag/eval_report_*.json)
	uv run python -m app.knowledge.evals.regression baseline --report $(or $(REPORT),$(shell ls -t evals/rag/eval_report_*.json 2>/dev/null | head -1)) --qa-file $(or $(QA_FILE),evals/rag/qa_pairs.jsonl) --force

rag-eval-check: ## Run RAG eval regression check against baseline (CI gate)
	uv run python -m app.knowledge.evals.regression check --report $(or $(REPORT),$(shell ls -t evals/rag/eval_report_*.json 2>/dev/null | head -1)) --qa-file $(or $(QA_FILE),evals/rag/qa_pairs.jsonl)

# === Ops ===

validate-alerts: ## Validate Prometheus alert rules YAML structure
	@uv run python -c "import yaml, sys; rules = yaml.safe_load(open('ops/prometheus/alerts.yml')); assert 'groups' in rules, 'Missing groups key'; print(f'{sum(len(g[\"rules\"]) for g in rules[\"groups\"])} alert rules validated')"
	@echo "Note: Install promtool for full validation: promtool check rules ops/prometheus/alerts.yml"

audit-log-taxonomy: ## Audit structured log events against docs/logging-standard.md
	uv run python scripts/audit_log_taxonomy.py

# === Security ===

install-hooks: ## Install git pre-commit hooks (pre-commit framework + legacy script)
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "Pre-commit hooks installed via pre-commit framework."

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

# === Deploy ===

PROD_HOST ?= root@204.168.156.137
PROD_DIR ?= ~/VTV

ship: ## Commit all changes, push, and deploy to production
	@echo "==> Staging all changes..."
	git add -A
	@echo "==> Committing..."
	git commit -m "$$(git diff --cached --stat | tail -1 | sed 's/^ /chore: /')" || echo "Nothing to commit"
	@echo "==> Pushing to origin..."
	git push origin main
	@echo "==> Deploying on $(PROD_HOST)..."
	ssh $(PROD_HOST) 'cd $(PROD_DIR) && git pull origin main && docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml up -d --build'
	@echo "==> Ship complete! Site: http://204.168.156.137"

deploy: ## Deploy to production (git push + rebuild containers on server)
	@echo "==> Pushing to origin..."
	git push origin main
	@echo "==> Deploying on $(PROD_HOST)..."
	ssh $(PROD_HOST) 'cd $(PROD_DIR) && git pull origin main && docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml up -d --build'
	@echo "==> Deploy complete! Site: http://204.168.156.137"

deploy-quick: ## Deploy without rebuilding containers (code-only, faster)
	@echo "==> Pushing to origin..."
	git push origin main
	@echo "==> Pulling code on $(PROD_HOST)..."
	ssh $(PROD_HOST) 'cd $(PROD_DIR) && git pull origin main && docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml restart cms app'
	@echo "==> Deploy complete! Site: http://204.168.156.137"

# === Help ===

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
