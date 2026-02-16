---
description: Initialize and validate the VTV development environment
argument-hint:
allowed-tools: Bash(python3 --version:*), Bash(uv --version:*), Bash(docker --version:*), Bash(docker-compose:*), Bash(curl:*)
---

Bootstrap the VTV development environment — verify tools, start services, confirm health.

Initialize and validate the VTV project. Run each step in order.

## 1. Check prerequisites

```
!python3 --version
!uv --version
!docker --version
!docker-compose --version
```

Required: Python 3.12+, uv, Docker, Docker Compose. If Docker daemon is not running, tell the user to open Docker Desktop first.

## 2. Start services

```
!docker-compose up -d
```

## 3. Verify containers are running

```
!docker-compose ps
```

Both `vtv-db-1` and `vtv-app-1` should show as running. DB should be healthy.

## 4. Verify API is healthy

```
!curl -s http://localhost:8123/health | python3 -m json.tool
```

Should return `{"status": "healthy", "service": "api"}`.

## 5. Report results

Tell the user:
- Whether all prerequisites are installed
- Whether containers started successfully
- Whether the health check passed
- The Swagger UI is at http://localhost:8123/docs

**Next step:** Run `/be-prime` to load project context into this session.
