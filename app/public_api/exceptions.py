"""Public API exception classes.

Inherits from core exceptions for automatic HTTP status code mapping:
- InvalidAPIKeyError -> 401 (custom handler)
- APIKeyRevokedError -> 401 (custom handler)
- APIKeyRateLimitError -> 429 (custom handler)
"""

from app.core.exceptions import AppError


class InvalidAPIKeyError(AppError):
    """API key missing, invalid, or expired."""


class APIKeyRevokedError(AppError):
    """API key has been revoked."""


class APIKeyRateLimitError(AppError):
    """Per-key rate limit exceeded."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after
