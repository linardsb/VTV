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

import uvicorn
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler  # pyright: ignore[reportMissingTypeStubs]
from slowapi.errors import RateLimitExceeded  # pyright: ignore[reportMissingTypeStubs]

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
from app.knowledge.routes import router as knowledge_router
from app.stops.routes import router as stops_router
from app.transit.poller import start_pollers, stop_pollers
from app.transit.routes import router as transit_router
from app.transit.service import close_transit_service

settings = get_settings()


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

    yield

    # Shutdown
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
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
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
app.include_router(agent_router)
app.include_router(transit_router)
app.include_router(stops_router)
app.include_router(knowledge_router)


@app.get("/")
def read_root() -> dict[str, str]:
    """Root endpoint providing API information.

    Returns:
        Dict containing application name, version, and docs URL.
    """
    return {
        "message": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
    }


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
