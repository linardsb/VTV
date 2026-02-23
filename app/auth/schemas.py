"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr, field_validator

PASSWORD_MIN_LENGTH = 10


def _validate_password_complexity(password: str) -> str:
    """Validate password meets government-grade complexity requirements.

    Args:
        password: The password string to validate.

    Returns:
        The validated password string.

    Raises:
        ValueError: If password does not meet complexity requirements.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        msg = f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
        raise ValueError(msg)
    if not any(c.isupper() for c in password):
        msg = "Password must contain at least one uppercase letter"
        raise ValueError(msg)
    if not any(c.islower() for c in password):
        msg = "Password must contain at least one lowercase letter"
        raise ValueError(msg)
    if not any(c.isdigit() for c in password):
        msg = "Password must contain at least one digit"
        raise ValueError(msg)
    return password


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Successful login response — returned to frontend auth.ts.

    NOTE: Tokens are returned in the response body (not httpOnly cookies) because
    Auth.js JWT strategy encrypts and stores them in its own httpOnly session cookie.
    The refresh_token is never exposed to client-side JavaScript directly.
    """

    id: int
    email: str
    name: str
    role: str
    access_token: str
    refresh_token: str


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Token refresh response."""

    access_token: str


class PasswordResetRequest(BaseModel):
    """Admin-initiated password reset."""

    user_id: int
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce password complexity on new passwords."""
        return _validate_password_complexity(v)


class UserResponse(BaseModel):
    """Public user information."""

    id: int
    email: str
    name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
