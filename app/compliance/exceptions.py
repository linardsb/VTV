"""Domain exceptions for NeTEx/SIRI compliance exports."""

from app.core.exceptions import AppError, DomainValidationError


class ComplianceError(AppError):
    """Base exception for compliance export errors."""


class ComplianceExportError(ComplianceError):
    """Exception raised when XML generation fails."""


class ComplianceValidationError(DomainValidationError):
    """Exception raised for invalid export parameters."""
