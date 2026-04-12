# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Prometheus HTTP request metrics middleware (OPS-2.1).

Records request latency histogram using FastAPI's resolved route path template
(not the raw URL) to keep label cardinality finite. Unmatched routes (404s)
collapse to ``__not_found__``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from app.core.config import get_settings
from app.core.metrics import REQUEST_LATENCY


def _resolve_path_template(request: Request) -> str:
    """Extract the route path template from a FastAPI request.

    Falls back to ``__not_found__`` for unmatched routes to prevent
    cardinality explosion from random 404 paths.
    """
    app = request.app
    for route in app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return "__not_found__"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record HTTP request duration in a Prometheus histogram."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not get_settings().metrics_enabled:
            return await call_next(request)

        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        path_template = _resolve_path_template(request)
        REQUEST_LATENCY.labels(
            method=request.method,
            path=path_template,
            status=response.status_code,
        ).observe(duration)

        return response
