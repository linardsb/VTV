---
description: Initialize and validate the VTV development environment
argument-hint:
allowed-tools: Bash(python3 --version:*), Bash(uv --version:*), Bash(docker --version:*), Bash(docker-compose:*), Bash(curl:*)
---

This command bootstraps the VTV development environment from scratch. It verifies that all required tooling is installed (Python 3.12+, uv package manager, Docker, and Docker Compose), starts the application's Docker services, and confirms everything is healthy. Run this at the start of a new session, after a system reboot, or whenever you suspect services may be down.

The command follows a strict sequential order: prerequisites first, then service startup, then health verification. If Docker Desktop is not running, it will stop and ask you to launch it before retrying. This prevents wasted time debugging container failures that are simply caused by the daemon being offline.

Once complete, you'll get a clear status report showing which tools are installed, whether containers are running and healthy, and whether the API is responding. It also provides the Swagger UI URL so you can immediately start exploring endpoints.

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
