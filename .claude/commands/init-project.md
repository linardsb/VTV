Initialize and validate the VTV project. Run each step in order.

## 1. Check prerequisites

Run these and confirm all are installed:

```bash
python3 --version
uv --version
docker --version
docker-compose --version
```

Required: Python 3.12+, uv, Docker, Docker Compose. If Docker daemon is not running, tell the user to open Docker Desktop first.

## 2. Start services

```bash
docker-compose up -d
```

## 3. Verify containers are running

```bash
docker-compose ps
```

Both `vtv-db-1` and `vtv-app-1` should show as running. DB should be healthy.

## 4. Verify API is healthy

```bash
curl -s http://localhost:8123/health | python3 -m json.tool
```

Should return `{"status": "healthy", "service": "api"}`.

## 5. Report results

Tell the user:
- Whether all prerequisites are installed
- Whether containers started successfully
- Whether the health check passed
- The Swagger UI is at http://localhost:8123/docs
