# Credential Rotation Runbook

> **Audience:** On-call engineers. Each section is self-contained - you can rotate any single credential without reading the full document.

## Prerequisites

- SSH access to Hetzner production host
- `.env.production` editor access
- GitHub repo admin (for GitHub Secrets)
- Provider dashboard access (Anthropic, Google, Groq, Jina, GlitchTip)

## Quick Reference

| Secret | Downtime | User Impact | Section |
|--------|----------|-------------|---------|
| JWT_SECRET_KEY | ~15s restart | All sessions invalidated | [S1](#1-jwt_secret_key) |
| AUTH_SECRET | ~10s restart | All CMS sessions invalidated | [S2](#2-auth_secret) |
| POSTGRES_PASSWORD | ~15s restart | Brief API unavailability | [S3](#3-postgresql-password) |
| REDIS_PASSWORD | ~10s restart | Cache flush, rate limits reset | [S4](#4-redis-password) |
| ANTHROPIC_API_KEY | ~15s restart | None (fallback chain) | [S5](#5-llm-api-keys-anthropic--google--groq) |
| GOOGLE_API_KEY | ~15s restart | None (fallback chain) | [S5](#5-llm-api-keys-anthropic--google--groq) |
| GROQ_API_KEY | ~15s restart | None (fallback chain) | [S5](#5-llm-api-keys-anthropic--google--groq) |
| EMBEDDING_API_KEY | ~15s restart | Search degraded briefly | [S6](#6-embedding-api-key) |
| SENTRY_DSN | ~15s restart | None (monitoring gap) | [S7](#7-glitchtipsentry-dsn) |
| HETZNER_SSH_KEY | 0s | None (CI-only) | [S8](#8-hetzner-ssh-key) |
| HETZNER_HOST | 0s | None (CI-only) | [S8](#8-hetzner-ssh-key) |
| TRACCAR_WEBHOOK_TOKEN | ~15s restart | Fleet tracking gap | [S9](#9-traccar-webhook-token) |
| SSL Certificates | 0s (reload) | None | [S10](#10-ssl-certificates) |
| GitHub Actions Secrets | 0s | None (CI-only) | [S11](#11-github-actions-secrets) |

## General Procedure

Every rotation follows this pattern:

1. SSH into production: `ssh root@<HETZNER_HOST>`
2. Navigate: `cd /root/VTV` (or wherever repo lives)
3. Backup current env: `cp .env.production .env.production.bak.$(date +%Y%m%d%H%M%S)`
4. Edit the secret: `nano .env.production`
5. Restart affected services (see per-secret section)
6. Verify via health endpoints
7. If verification fails: `cp .env.production.bak.* .env.production && docker compose ... up -d --build`

---

## 1. JWT_SECRET_KEY

### Location

- **Env var:** `JWT_SECRET_KEY`
- **File:** `.env.production` on Hetzner host
- **Used by:** `app/auth/token.py` - HS256 JWT signing
- **Startup validation:** Rejects defaults and keys <32 chars in non-dev (`app/core/config.py`)

### Rotation Command

```bash
# Generate new key
NEW_KEY=$(openssl rand -base64 32)
echo "New JWT_SECRET_KEY: $NEW_KEY"

# Update .env.production
sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$NEW_KEY|" .env.production

# Restart app + CMS (both use JWT validation)
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app cms
```

### Downtime

- **Duration:** ~15 seconds (app + CMS restart)
- **User impact:** ALL active JWT tokens (access + refresh) are immediately invalidated. Every logged-in user must re-authenticate.
- **Mitigation:** Schedule during low-traffic window. Warn users if possible.

### Verification

```bash
# 1. Health check
curl -sf http://localhost:80/health | jq .
# Expected: {"status": "healthy", "service": "api"}

# 2. Login works with new key
curl -X POST http://localhost:80/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<admin_password>"}' | jq .token

# 3. No errors in logs
docker compose logs app --tail 50 | grep -i "error\|jwt\|secret"
```

### Rollback

```bash
cp .env.production.bak.* .env.production  # Restore old key
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app cms
# Note: tokens issued with the NEW key during the rotation window will be invalidated on rollback
```

---

## 2. AUTH_SECRET

### Location

- **Env var:** `AUTH_SECRET`
- **File:** `.env.production` on Hetzner host
- **Used by:** `cms/apps/web/auth.ts` - NextAuth v5 session encryption
- **Prod validation:** `docker-compose.prod.yml` - `${AUTH_SECRET:?Set AUTH_SECRET}`

### Rotation Command

```bash
NEW_SECRET=$(openssl rand -base64 32)
sed -i "s|^AUTH_SECRET=.*|AUTH_SECRET=$NEW_SECRET|" .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart cms
```

### Downtime

- **Duration:** ~10 seconds (CMS restart only)
- **User impact:** All CMS dashboard sessions invalidated. Users must re-login to the CMS.
- **API users unaffected** (JWT tokens are independent of AUTH_SECRET).

### Verification

```bash
# CMS responds
curl -sf http://localhost:80/ | head -5

# CMS login page loads
curl -sf http://localhost:80/lv/login -o /dev/null && echo "OK"

# No auth errors
docker compose logs cms --tail 30 | grep -i "error\|auth"
```

### Rollback

```bash
cp .env.production.bak.* .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart cms
```

---

## 3. PostgreSQL Password

### Location

- **Env var:** `POSTGRES_PASSWORD` (interpolated into `DATABASE_URL`)
- **File:** `.env.production` on Hetzner host
- **Used by:** PostgreSQL server auth + app/migrate connection strings
- **Prod validation:** `${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}` in `docker-compose.prod.yml`

### Rotation Command

```bash
NEW_PW=$(openssl rand -base64 24 | tr -d '=/+')  # URL-safe

# Step 1: Change password inside running PostgreSQL
docker compose exec db psql -U postgres -c "ALTER USER postgres WITH PASSWORD '$NEW_PW';"

# Step 2: Update .env.production
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_PW|" .env.production

# Step 3: Restart app + migrate (they read DATABASE_URL from env)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build app
# Note: Do NOT restart db - the password was already changed via ALTER USER
```

### Downtime

- **Duration:** ~15 seconds (app restart)
- **User impact:** Brief API unavailability during restart. No data loss.
- **DB connections:** Pool (3 base + 5 overflow per worker) drains gracefully in 30s.

### Verification

```bash
# DB health
curl -sf http://localhost:80/health/db | jq .
# Expected: {"status": "healthy", "service": "database"}

# Full readiness
curl -sf http://localhost:80/health/ready | jq .

# Migrations still work
docker compose exec app alembic current
```

### Rollback

```bash
# Revert password in PostgreSQL
docker compose exec db psql -U postgres -c "ALTER USER postgres WITH PASSWORD '<OLD_PASSWORD>';"
# Revert .env.production
cp .env.production.bak.* .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app
```

---

## 4. Redis Password

### Location

- **Env var:** `REDIS_PASSWORD` (interpolated into `REDIS_URL`)
- **File:** `.env.production` on Hetzner host
- **Used by:** Redis server `--requirepass` + app/CMS connection URL
- **Note:** Redis is stateless cache - data loss on restart is acceptable

### Rotation Command

```bash
NEW_PW=$(openssl rand -base64 24 | tr -d '=/+')

# Update .env.production
sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$NEW_PW|" .env.production

# Restart Redis (picks up new --requirepass) + app (picks up new REDIS_URL)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build redis app
```

### Downtime

- **Duration:** ~10 seconds
- **User impact:** Cache flush (vehicle positions re-fetched on next poll cycle ~15s). Rate limit counters reset. Token revocation denylist cleared (active revoked tokens temporarily valid until they expire naturally, max 30 min).

### Verification

```bash
curl -sf http://localhost:80/health/redis | jq .
# Expected: {"status": "healthy", "service": "redis"}

# Confirm rate limiting works
for i in {1..5}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:80/health; done
```

### Rollback

```bash
cp .env.production.bak.* .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build redis app
```

---

## 5. LLM API Keys (Anthropic / Google / Groq)

### Location

- **Env vars:** `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`
- **File:** `.env.production` on Hetzner host
- **Used by:** `app/core/agents/config.py` - provider initialization
- **Fallback:** Circuit breaker + `LLM_FALLBACK_PROVIDER` cascades to next provider

### Rotation Command (example: Anthropic)

```bash
# 1. Generate new key at https://console.anthropic.com/settings/keys
# 2. Update .env.production
sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=<new-key>|" .env.production

# 3. Restart app
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app
```

Same pattern for `GOOGLE_API_KEY` (Google AI Studio) and `GROQ_API_KEY` (Groq Console).

### Downtime

- **Duration:** ~15 seconds (app restart)
- **User impact:** None if fallback provider is configured. If this is the only provider, chat/agent features unavailable during restart.
- **Circuit breaker:** If old key was revoked before restart, breaker opens and routes to fallback automatically.

### Verification

```bash
# App healthy
curl -sf http://localhost:80/health | jq .

# Agent responds (requires auth token)
curl -X POST http://localhost:80/api/v1/agent/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "ping"}' | jq .status

# Check logs for provider errors
docker compose logs app --tail 30 | grep -i "provider\|llm\|anthropic\|circuit"
```

### Rollback

```bash
cp .env.production.bak.* .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app
```

---

## 6. Embedding API Key

### Location

- **Env var:** `EMBEDDING_API_KEY`
- **File:** `.env.production` on Hetzner host
- **Used by:** `app/knowledge/embedding.py` - Jina/OpenAI embedding calls
- **Provider dashboard:** Jina AI (https://jina.ai/api-key) or OpenAI Platform

### Rotation Command

```bash
# 1. Generate new key at provider dashboard
# 2. Update
sed -i "s|^EMBEDDING_API_KEY=.*|EMBEDDING_API_KEY=<new-key>|" .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app
```

### Downtime

- **Duration:** ~15 seconds
- **User impact:** Knowledge base search/RAG briefly unavailable during restart. Existing embeddings in pgvector unaffected.

### Verification

```bash
curl -sf http://localhost:80/health | jq .

# Test knowledge search (requires auth)
curl -X POST http://localhost:80/api/v1/knowledge/search \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' | jq '.results | length'
```

### Rollback

```bash
cp .env.production.bak.* .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app
```

---

## 7. GlitchTip/Sentry DSN

### Location

- **Env var:** `SENTRY_DSN`
- **File:** `.env.production` on Hetzner host
- **Used by:** `app/core/config.py` - error tracking initialization
- **Dashboard:** GlitchTip project settings

### Rotation Command

```bash
# 1. Create new DSN in GlitchTip: Settings > Projects > VTV > Client Keys > Generate
# 2. Update
sed -i "s|^SENTRY_DSN=.*|SENTRY_DSN=<new-dsn-url>|" .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app
```

### Downtime

- **Duration:** ~15 seconds
- **User impact:** None. Error tracking has a brief gap - errors during restart are not captured.

### Verification

```bash
# Trigger a test error (if you have a test endpoint) or check GlitchTip dashboard
# for new events after restart

docker compose logs app --tail 10 | grep -i "sentry\|glitchtip"
```

### Rollback

```bash
cp .env.production.bak.* .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart app
# Old DSN continues to work unless explicitly revoked in GlitchTip
```

---

## 8. Hetzner SSH Key

### Location

- **GitHub Secret:** `HETZNER_SSH_KEY` (PEM private key)
- **GitHub Secret:** `HETZNER_HOST` (IP address)
- **Used by:** `.github/workflows/deploy.yml` - `appleboy/ssh-action@v1`

### Rotation Command

```bash
# 1. Generate new SSH key pair (on your local machine)
ssh-keygen -t ed25519 -C "vtv-deploy" -f vtv-deploy-key

# 2. Add public key to Hetzner server
ssh root@<HETZNER_HOST> "cat >> ~/.ssh/authorized_keys" < vtv-deploy-key.pub

# 3. Test SSH access with new key
ssh -i vtv-deploy-key root@<HETZNER_HOST> "echo OK"

# 4. Update GitHub Secret
# Go to: github.com/<org>/VTV/settings/secrets/actions
# Update HETZNER_SSH_KEY with contents of vtv-deploy-key (private key)

# 5. Remove old public key from server (after confirming new key works)
ssh -i vtv-deploy-key root@<HETZNER_HOST>
# Edit ~/.ssh/authorized_keys and remove the old key line

# 6. Delete local key files
rm vtv-deploy-key vtv-deploy-key.pub
```

### Downtime

- **Duration:** 0 seconds
- **User impact:** None. Only affects CI/CD pipeline. Deploys fail until GitHub Secret is updated.

### Verification

```bash
# Trigger a deployment (push to main or manual workflow dispatch)
# Check GitHub Actions: github.com/<org>/VTV/actions
# Deploy job should succeed with new key
```

### Rollback

```bash
# Re-add old public key to server's authorized_keys
# Revert HETZNER_SSH_KEY GitHub Secret to old private key
```

---

## 9. Traccar Webhook Token

### Location

- **Env var:** `TRACCAR_WEBHOOK_TOKEN`
- **File:** `.env.production` on Hetzner host
- **Used by:** `app/fleet/` - webhook authentication for GPS data ingestion
- **Startup validation:** Rejects default `vtv-traccar-webhook` in prod (`app/core/config.py`)
- **Only relevant when:** `TRACCAR_ENABLED=true`

### Rotation Command

```bash
NEW_TOKEN=$(openssl rand -hex 32)
sed -i "s|^TRACCAR_WEBHOOK_TOKEN=.*|TRACCAR_WEBHOOK_TOKEN=$NEW_TOKEN|" .env.production

# Restart app (validates incoming webhooks) + Traccar (sends webhooks)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile fleet restart app traccar
# Update Traccar's webhook URL to include new token (Traccar admin UI or traccar.xml)
```

### Downtime

- **Duration:** ~15 seconds
- **User impact:** Fleet GPS tracking gap during restart. Vehicle positions resume on next poll.

### Verification

```bash
curl -sf http://localhost:80/health | jq .
# Check fleet device positions are updating
docker compose logs app --tail 20 | grep -i "traccar\|fleet\|webhook"
```

### Rollback

```bash
cp .env.production.bak.* .env.production
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile fleet restart app traccar
```

---

## 10. SSL Certificates

### Location

- **Volume mount:** `/etc/nginx/certs/cert.pem` + `/etc/nginx/certs/key.pem`
- **Config:** `nginx/nginx.prod.conf` (if HTTPS enabled)
- **Used by:** Nginx TLS termination

### Rotation Command

```bash
# 1. Obtain new certificate (Let's Encrypt example)
certbot certonly --standalone -d vtv.example.lv

# 2. Copy to nginx certs volume
cp /etc/letsencrypt/live/vtv.example.lv/fullchain.pem /path/to/certs/cert.pem
cp /etc/letsencrypt/live/vtv.example.lv/privkey.pem /path/to/certs/key.pem

# 3. Reload nginx (zero-downtime)
docker compose exec nginx nginx -s reload
```

### Downtime

- **Duration:** 0 seconds (`nginx -s reload` preserves active connections)
- **User impact:** None.

### Verification

```bash
# Check certificate expiry
echo | openssl s_client -connect vtv.example.lv:443 2>/dev/null | openssl x509 -noout -dates

# HTTPS health check
curl -sf https://vtv.example.lv/health | jq .
```

### Rollback

```bash
# Restore old certificates and reload
cp /path/to/backup/cert.pem /path/to/certs/cert.pem
cp /path/to/backup/key.pem /path/to/certs/key.pem
docker compose exec nginx nginx -s reload
```

---

## 11. GitHub Actions Secrets

### Location

- **GitHub UI:** `github.com/<org>/VTV/settings/secrets/actions`
- **Secrets used in CI/CD:** `HETZNER_HOST`, `HETZNER_SSH_KEY`

### Rotation Command

1. Go to `github.com/<org>/VTV/settings/secrets/actions`
2. Click the secret to update
3. Enter new value, click Update secret
4. Trigger a test workflow run to verify

### Downtime

- **Duration:** 0 seconds
- **User impact:** None. Only CI/CD pipelines are affected.

### Verification

- Push a commit or manually trigger the deploy workflow
- Verify the workflow succeeds in GitHub Actions UI

---

## Emergency Rotation (All Secrets at Once)

If a full credential compromise is suspected:

```bash
# 1. SSH to production
ssh root@<HETZNER_HOST>
cd /root/VTV

# 2. Backup everything
cp .env.production .env.production.bak.$(date +%Y%m%d%H%M%S)
./scripts/db-backup.sh

# 3. Generate all new secrets
JWT_SECRET_KEY=$(openssl rand -base64 32)
AUTH_SECRET=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '=/+')
REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '=/+')
TRACCAR_WEBHOOK_TOKEN=$(openssl rand -hex 32)

# 4. Change PostgreSQL password FIRST (while old cred still works)
docker compose exec db psql -U postgres -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"

# 5. Update .env.production with all new values
nano .env.production  # Apply all changes

# 6. Rotate API keys at provider dashboards
# - Anthropic: console.anthropic.com/settings/keys
# - Google: aistudio.google.com/apikey
# - Groq: console.groq.com/keys
# - Jina: jina.ai/api-key
# - GlitchTip: project settings > client keys

# 7. Full stack restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 8. Verify all health checks
curl -sf http://localhost:80/health/ready | jq .

# 9. Update GitHub Secrets (HETZNER_SSH_KEY if compromised)
# 10. Revoke old API keys at each provider dashboard
```

**Expected total downtime:** 1-3 minutes. All user sessions invalidated.
