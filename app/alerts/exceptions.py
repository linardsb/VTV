"""Feature-specific exceptions for the notification/alerts feature.

Inherits from core exceptions for automatic HTTP status code mapping:
- AlertNotFoundError -> 404
- AlertRuleNotFoundError -> 404
- AlertError -> 500
"""

from app.core.exceptions import AppError, NotFoundError


class AlertError(AppError):
    """Base exception for alert-related errors."""


class AlertNotFoundError(NotFoundError):
    """Raised when an alert instance is not found by ID."""


class AlertRuleNotFoundError(NotFoundError):
    """Raised when an alert rule is not found by ID."""
