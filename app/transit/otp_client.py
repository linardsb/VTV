# pyright: reportUnknownMemberType=false
"""HTTP client for the OpenTripPlanner /plan API with circuit breaker protection."""

from typing import Any

import httpx

from app.core.agents.exceptions import TransitDataError
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.resilience import CircuitBreaker

logger = get_logger(__name__)


class OTPClient:
    """Thin async HTTP wrapper around the OTP 2.x REST API.

    Uses a circuit breaker to avoid hammering an unhealthy OTP instance.
    """

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http_client
        self._base_url = settings.otp_base_url.rstrip("/")
        self._router_id = settings.otp_router_id
        self._breaker = CircuitBreaker(
            name="otp-planner",
            failure_threshold=5,
            reset_timeout=60.0,
        )

    async def plan(self, params: dict[str, str]) -> dict[str, Any]:
        """Call OTP /plan endpoint and return the raw JSON response.

        Args:
            params: OTP query parameters (fromPlace, toPlace, date, time, etc.).

        Returns:
            Parsed JSON response from OTP.

        Raises:
            TransitDataError: On HTTP errors, connection failures, or open circuit.
        """
        url = f"{self._base_url}/otp/routers/{self._router_id}/plan"
        result: dict[str, Any] = {}
        try:
            async with self._breaker:
                response = await self._http.get(url, params=params)
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "transit.otp_client.plan_http_error",
                status_code=exc.response.status_code,
                url=url,
            )
            raise TransitDataError(f"OTP returned HTTP {exc.response.status_code}") from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "transit.otp_client.plan_connection_failed",
                error=str(exc),
            )
            raise TransitDataError("OTP connection failed") from exc
        except TransitDataError:
            raise
        except Exception as exc:
            logger.warning(
                "transit.otp_client.plan_failed",
                error=str(exc),
            )
            raise TransitDataError("OTP request failed") from exc
        return result
