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
from slowapi.errors import RateLimitExceeded  # pyright: ignore[reportMissingTypeStubs]

from app.alerts.crowding_evaluator import start_crowding_evaluator, stop_crowding_evaluator
from app.alerts.evaluator import start_evaluator, stop_evaluator
from app.alerts.routes import router as alerts_router
from app.analytics.daily_adherence import start_adherence_task, stop_adherence_task
from app.analytics.routes import router as analytics_router
from app.auth.routes import router as auth_router
from app.compliance.routes import router as compliance_router
from app.core.agents.agents.registry import close_all_agents
from app.core.agents.exceptions import setup_agent_exception_handlers
from app.core.agents.routes import router as agent_router
from app.core.agents.service import close_agent_service
from app.core.auth.routes import audit_router
from app.core.auth.routes import router as assignments_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import setup_exception_handlers
from app.core.health import router as health_router
from app.core.jobs.queue import close_arq_pool, get_arq_pool
from app.core.jobs.routes import router as jobs_router
from app.core.logging import get_logger, setup_logging
from app.core.metrics_middleware import MetricsMiddleware
from app.core.middleware import setup_middleware
from app.core.rate_limit import RateLimitIdentityMiddleware, limiter, rate_limit_exceeded_handler
from app.core.redis import close_redis
from app.core.shutdown import ShutdownCoordinator, ShutdownTask
from app.drivers.routes import router as drivers_router
from app.events.routes import router as events_router
from app.fleet.routes import router as fleet_router
from app.geofences.evaluator import start_geofence_evaluator, stop_geofence_evaluator
from app.geofences.routes import router as geofences_router
from app.knowledge.lifecycle import start_knowledge_tasks, stop_knowledge_tasks
from app.knowledge.routes import router as knowledge_router
from app.memory.lifecycle import start_memory_tasks, stop_memory_tasks
from app.memory.routes import router as memory_router
from app.ml.anomaly.evaluator import start_anomaly_evaluator, stop_anomaly_evaluator
from app.ml.anomaly.off_route import start_off_route_evaluator, stop_off_route_evaluator
from app.ml.anomaly.routes import router as anomaly_router
from app.public_api.routes import key_mgmt_router as public_api_key_mgmt_router
from app.public_api.routes import public_router as public_api_router
from app.schedules.feed_task import start_feed_import_task, stop_feed_import_task
from app.schedules.routes import router as schedules_router
from app.skills.routes import router as skills_router
from app.stops.routes import router as stops_router
from app.transit.poller import start_pollers, stop_pollers
from app.transit.routes import router as transit_router
from app.transit.service import close_transit_service
from app.transit.traffic_etl import start_traffic_etl, stop_traffic_etl
from app.transit.weather_etl import start_weather_etl, stop_weather_etl
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

    # Start alert evaluator background task
    await start_evaluator(settings)

    # Start geofence evaluator background task
    await start_geofence_evaluator(settings)

    # Start crowding prediction evaluator (ML-3.3)
    await start_crowding_evaluator(settings)

    # Start anomaly detection evaluator (ML-4.2)
    await start_anomaly_evaluator(settings)

    # Start off-route anomaly evaluator (ML-4.1)
    await start_off_route_evaluator(settings)

    # Start daily adherence report background task (ML-5.2)
    await start_adherence_task()

    # Start memory background tasks (compaction + promotion)
    await start_memory_tasks()

    # Start knowledge RRF recompute loop (KB-4, in-process fallback)
    await start_knowledge_tasks()

    # Initialize arq pool for durable job queue (OPS-3.2)
    if settings.background_queue_enabled:
        await get_arq_pool()
        logger.info("jobs.queue.lifecycle_started")

    # Start weather ETL background task (ML-1.3)
    await start_weather_etl()

    # Start traffic ETL background task (ML-1.3)
    await start_traffic_etl()

    # Start daily GTFS feed import task (LV-1.2)
    await start_feed_import_task()

    # Start train WebSocket listener (LV-2.2)
    if settings.train_ws_enabled:
        from app.transit.train_ws_listener import start_train_ws_listener

        await start_train_ws_listener(settings)

    # Start OwnTracks MQTT listener (LV-3.1)
    if settings.owntracks_mqtt_enabled:
        from app.transit.owntracks_listener import start_owntracks_listener

        await start_owntracks_listener(settings)

    # Pre-load reranker model (avoids cold-start on first search)
    try:
        from app.knowledge.service import warm_up_reranker

        await warm_up_reranker()
    except Exception:
        logger.warning("knowledge.reranker.warm_up_failed", exc_info=True)

    # Pre-load Latvian UDPipe lemmatizer (KB-2) — non-fatal if model missing
    if settings.latvian_lemmatizer_enabled:
        try:
            from app.knowledge.service import warm_up_lemmatizer

            await warm_up_lemmatizer()
        except Exception:
            logger.warning(
                "knowledge.lemmatizer.warm_up_failed",
                exc_info=True,
                stage="startup_warmup",
            )

    # Start WebSocket subscriber (pushes Redis Pub/Sub -> WebSocket clients)
    if settings.ws_enabled and settings.poller_enabled:
        ws_manager = get_ws_manager()
        await start_ws_subscriber(ws_manager)
        logger.info("transit.ws.subscriber_started")

    # Register shutdown tasks (LIFO: last registered = first drained)
    coordinator = ShutdownCoordinator()

    # Infrastructure singletons (drain last = register first)
    coordinator.register(ShutdownTask(name="database", drain_timeout_s=3.0, drain=engine.dispose))
    coordinator.register(ShutdownTask(name="redis", drain_timeout_s=2.0, drain=close_redis))
    coordinator.register(ShutdownTask(name="arq_pool", drain_timeout_s=2.0, drain=close_arq_pool))
    coordinator.register(
        ShutdownTask(name="agent_clients", drain_timeout_s=2.0, drain=close_all_agents)
    )
    coordinator.register(
        ShutdownTask(name="agent_service", drain_timeout_s=2.0, drain=close_agent_service)
    )
    coordinator.register(
        ShutdownTask(name="transit_service", drain_timeout_s=2.0, drain=close_transit_service)
    )

    # Background task groups (drain first = register last)
    coordinator.register(
        ShutdownTask(name="transit_pollers", drain_timeout_s=5.0, drain=stop_pollers)
    )

    # close_ws_manager is sync -- wrap it
    async def _close_ws() -> None:
        await stop_ws_subscriber()
        close_ws_manager()

    coordinator.register(ShutdownTask(name="websocket", drain_timeout_s=3.0, drain=_close_ws))
    coordinator.register(
        ShutdownTask(name="alert_evaluator", drain_timeout_s=3.0, drain=stop_evaluator)
    )
    coordinator.register(
        ShutdownTask(
            name="geofence_evaluator",
            drain_timeout_s=3.0,
            drain=stop_geofence_evaluator,
        )
    )
    coordinator.register(
        ShutdownTask(
            name="crowding_evaluator",
            drain_timeout_s=3.0,
            drain=stop_crowding_evaluator,
        )
    )
    coordinator.register(
        ShutdownTask(
            name="anomaly_evaluator",
            drain_timeout_s=3.0,
            drain=stop_anomaly_evaluator,
        )
    )
    coordinator.register(
        ShutdownTask(
            name="off_route_evaluator",
            drain_timeout_s=3.0,
            drain=stop_off_route_evaluator,
        )
    )
    coordinator.register(
        ShutdownTask(name="weather_etl", drain_timeout_s=3.0, drain=stop_weather_etl)
    )
    coordinator.register(
        ShutdownTask(name="traffic_etl", drain_timeout_s=3.0, drain=stop_traffic_etl)
    )
    coordinator.register(
        ShutdownTask(name="memory_tasks", drain_timeout_s=5.0, drain=stop_memory_tasks)
    )
    coordinator.register(
        ShutdownTask(name="knowledge_tasks", drain_timeout_s=5.0, drain=stop_knowledge_tasks)
    )
    coordinator.register(
        ShutdownTask(name="adherence_task", drain_timeout_s=3.0, drain=stop_adherence_task)
    )
    coordinator.register(
        ShutdownTask(
            name="gtfs_feed_import",
            drain_timeout_s=5.0,
            drain=stop_feed_import_task,
        )
    )

    if settings.train_ws_enabled:
        from app.transit.train_ws_listener import stop_train_ws_listener

        coordinator.register(
            ShutdownTask(
                name="train_ws_listener",
                drain_timeout_s=5.0,
                drain=stop_train_ws_listener,
            )
        )

    if settings.owntracks_mqtt_enabled:
        from app.transit.owntracks_listener import stop_owntracks_listener

        coordinator.register(
            ShutdownTask(
                name="owntracks_listener",
                drain_timeout_s=5.0,
                drain=stop_owntracks_listener,
            )
        )

    yield

    # Shutdown via coordinator
    report = await coordinator.shutdown()
    logger.info(
        "shutdown.report",
        tasks_drained=report.tasks_drained,
        tasks_timed_out=report.tasks_timed_out,
        tasks_failed=report.tasks_failed,
        total_duration_ms=report.total_duration_ms,
    )
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
app.add_exception_handler(RateLimitExceeded, cast(Any, rate_limit_exceeded_handler))

# Setup middleware
setup_middleware(app)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitIdentityMiddleware)  # OPS-4.1: populate user identity for rate limiting

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
app.include_router(memory_router)
app.include_router(schedules_router)
app.include_router(drivers_router)
app.include_router(events_router)
app.include_router(skills_router)
app.include_router(vehicles_router)
app.include_router(compliance_router)
app.include_router(analytics_router)
app.include_router(alerts_router)
app.include_router(fleet_router)
app.include_router(geofences_router)
app.include_router(public_api_key_mgmt_router)
app.include_router(public_api_router)
app.include_router(jobs_router)
app.include_router(assignments_router)
app.include_router(audit_router)
app.include_router(anomaly_router)

# Prometheus metrics endpoint (OPS-2.1)
# Access control via nginx IP allowlist — scrapers don't carry JWTs.
if get_settings().metrics_enabled:
    from prometheus_client import (
        make_asgi_app as _make_metrics_app,  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
    )

    app.mount("/metrics", _make_metrics_app())  # pyright: ignore[reportUnknownArgumentType]


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
