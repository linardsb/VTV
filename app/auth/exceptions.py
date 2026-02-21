"""Authentication-specific exceptions.

Inherits from core exceptions for automatic HTTP status code mapping:
- InvalidCredentialsError -> 401 (custom handler)
- AccountLockedError -> 423 (custom handler)
"""

from app.core.exceptions import AppError


class InvalidCredentialsError(AppError):
    """Raised when email/password combination is invalid."""


class AccountLockedError(AppError):
    """Raised when account is locked due to too many failed attempts."""
