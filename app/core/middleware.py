"""Request/response middleware for FastAPI application.

This module provides:
- Request logging middleware with correlation IDs
- Request ID extraction from headers or generation
- Request/response lifecycle logging
- CORS middleware setup
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.core.logging import get_logger, get_request_id, set_request_id

logger = get_logger(__name__)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that rejects request bodies exceeding a size limit.

    Prevents oversized payloads from consuming server memory. Returns
    HTTP 413 (Content Too Large) for requests exceeding the limit.
    """

    def __init__(self, app: ASGIApp, max_body_size: int = 102_400) -> None:
        """Initialize with the maximum allowed body size in bytes.

        Args:
            app: The ASGI application.
            max_body_size: Maximum allowed body size in bytes (default 100KB).
        """
        super().__init__(app)
        self._max_body_size = max_body_size

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Check Content-Length header and reject oversized requests.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            Response from the next handler, or 413 if body too large.
        """
        # Allow larger uploads for specific file-based endpoints
        path = request.url.path
        upload_paths = (
            "/api/v1/schedules/import",
            "/api/v1/schedules/validate",
            "/api/v1/knowledge",
        )
        if any(path.startswith(p) for p in upload_paths):
            max_size = 52_428_800  # 50MB + overhead for file uploads
        else:
            max_size = self._max_body_size

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid Content-Length header"},
                )
            if length > max_size:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request body too large", "max_bytes": max_size},
                )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging with correlation ID.

    This middleware:
    1. Extracts or generates a request ID for each request
    2. Sets the request ID in context for correlation across logs
    3. Logs request.http_received with method, path, and client info
    4. Logs request.http_completed with status code and duration
    5. Logs request.http_failed with full exception info on errors
    6. Adds X-Request-ID to response headers
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process each request and response.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            The response with X-Request-ID header added.

        Raises:
            Exception: Re-raises any exception after logging it.
        """
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID")
        set_request_id(request_id)

        start_time = time.time()
        logger.info(
            "request.http_received",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            logger.info(
                "request.http_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,  # pyright: ignore[reportUnknownMemberType]
                duration_seconds=round(duration, 3),
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = get_request_id()  # pyright: ignore[reportUnknownMemberType]
            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "request.http_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_seconds=round(duration, 3),
                exc_info=True,
            )
            raise


def setup_middleware(app: FastAPI) -> None:
    """Set up all middleware for the application.

    Adds:
    1. RequestLoggingMiddleware for request/response logging
    2. CORSMiddleware for cross-origin requests

    Args:
        app: The FastAPI application instance.
    """
    settings = get_settings()

    # Add body size limit (must be before logging to reject early)
    app.add_middleware(BodySizeLimitMiddleware, max_body_size=102_400)

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "Accept",
            "Accept-Language",
        ],
    )
