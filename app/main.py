"""FastAPI application entry point.

This module creates and configures the FastAPI application with:
- Lifespan event management for startup/shutdown
- Structured logging setup
- Request/response middleware
- CORS support
- Database connection management
- Health check endpoints
- Global exception handlers
- Root API endpoint
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import sentry_sdk
import uvicorn
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler  # pyright: ignore[reportMissingTypeStubs]
from slowapi.errors import RateLimitExceeded  # pyright: ignore[reportMissingTypeStubs]

from app.auth.routes import router as auth_router
from app.core.agents.exceptions import setup_agent_exception_handlers
from app.core.agents.routes import router as agent_router
from app.core.agents.service import close_agent_service
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import setup_exception_handlers
from app.core.health import router as health_router
from app.core.logging import get_logger, setup_logging
from app.core.middleware import setup_middleware
from app.core.rate_limit import limiter
from app.core.redis import close_redis
from app.drivers.routes import router as drivers_router
from app.events.routes import router as events_router
from app.knowledge.routes import router as knowledge_router
from app.schedules.routes import router as schedules_router
from app.skills.routes import router as skills_router
from app.stops.routes import router as stops_router
from app.transit.poller import start_pollers, stop_pollers
from app.transit.routes import router as transit_router
from app.transit.service import close_transit_service
from app.transit.ws_routes import close_ws_manager, get_ws_manager, ws_router
from app.transit.ws_subscriber import start_ws_subscriber, stop_ws_subscriber
from app.vehicles.routes import router as vehicles_router

settings = get_settings()

# Initialize Sentry/GlitchTip before anything else — noop if DSN is not configured
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"vtv@{settings.version}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        enable_tracing=True,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan event handler.

    Handles startup and shutdown logic:
    - Startup: Configure logging, initialize database connection, log application start
    - Shutdown: Dispose database connections, log application shutdown

    Args:
        _app: The FastAPI application instance (unused, required by protocol).

    Yields:
        None: Control returns to the application.
    """
    # Startup
    setup_logging(log_level=settings.log_level)
    logger = get_logger(__name__)

    # SECURITY: Fail hard if JWT secret is weak in non-development environments
    _insecure_defaults = {"CHANGE-ME-IN-PRODUCTION", "", "secret", "changeme"}
    if settings.environment != "development" and (
        settings.jwt_secret_key in _insecure_defaults or len(settings.jwt_secret_key) < 32
    ):
        msg = (
            "JWT_SECRET_KEY must be a strong secret (min 32 chars) in non-development environments"
        )
        raise RuntimeError(msg)

    logger.info(
        "application.lifecycle_started",
        app_name=settings.app_name,
        version=settings.version,
        environment=settings.environment,
    )
    logger.info("database.connection_initialized")

    # Start background pollers
    await start_pollers()
    logger.info("transit.poller.lifecycle_started")

    # Start WebSocket subscriber (pushes Redis Pub/Sub -> WebSocket clients)
    if settings.ws_enabled and settings.poller_enabled:
        ws_manager = get_ws_manager()
        await start_ws_subscriber(ws_manager)
        logger.info("transit.ws.subscriber_started")

    yield

    # Shutdown
    await stop_ws_subscriber()
    close_ws_manager()
    logger.info("transit.ws.lifecycle_stopped")
    await stop_pollers()
    logger.info("transit.poller.lifecycle_stopped")
    await close_transit_service()
    await close_agent_service()
    logger.info("security.singletons_closed")
    await close_redis()
    await engine.dispose()
    logger.info("database.connection_closed")
    logger.info("application.lifecycle_stopped", app_name=settings.app_name)


# Create FastAPI application
# Disable interactive docs in production (defense-in-depth with nginx)
_is_dev = settings.environment == "development"

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
)

# Setup rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, cast(Any, _rate_limit_exceeded_handler))

# Setup middleware
setup_middleware(app)

# Setup exception handlers
setup_exception_handlers(app)
setup_agent_exception_handlers(app)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(transit_router)
app.include_router(ws_router)
app.include_router(stops_router)
app.include_router(knowledge_router)
app.include_router(schedules_router)
app.include_router(drivers_router)
app.include_router(events_router)
app.include_router(skills_router)
app.include_router(vehicles_router)


@app.get("/")
def read_root() -> dict[str, str]:
    """Root endpoint providing API information.

    Returns:
        Dict containing application name, version, and docs URL.
    """
    response: dict[str, str] = {"message": settings.app_name}
    if settings.environment == "development":
        response["version"] = settings.version
        response["docs"] = "/docs"
    return response


if __name__ == "__main__":
    # S104: Binding to 0.0.0.0 is intentional for development/container environments.
    # This code path is ONLY used for:
    # 1. Local development (note reload=True)
    # 2. Docker containers where binding to all interfaces is required
    #
    # PRODUCTION DEPLOYMENT: Always use uvicorn CLI or gunicorn with explicit
    # host configuration (e.g., --host 127.0.0.1) instead of running this file directly.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104
        port=8123,
        reload=True,
    )
