"""Feature-specific exceptions for agent skills.

Inherits from core exceptions for automatic HTTP status code mapping:
- SkillNotFoundError -> 404
- SkillValidationError -> 422
- SkillError -> 500
"""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class SkillError(AppError):
    """Base exception for skill-related errors."""


class SkillNotFoundError(NotFoundError):
    """Raised when an agent skill is not found by ID."""


class SkillValidationError(DomainValidationError):
    """Raised when skill data fails validation (e.g., duplicate name)."""
