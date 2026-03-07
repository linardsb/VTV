"""Pydantic schemas for authentication."""

import datetime

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
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        msg = "Password must contain at least one special character"
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


class UserDetailResponse(BaseModel):
    """User detail with timestamps."""

    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


_VALID_ROLES = {"admin", "dispatcher", "editor", "viewer"}


class CreateUserRequest(BaseModel):
    """Admin creates a new user."""

    email: EmailStr
    name: str
    password: str
    role: str = "viewer"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce password complexity."""
        return _validate_password_complexity(v)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Ensure role is one of the 4 valid VTV roles."""
        if v not in _VALID_ROLES:
            msg = f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}"
            raise ValueError(msg)
        return v


class UpdateUserRequest(BaseModel):
    """Admin updates user fields."""

    name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        """Ensure role is one of the 4 valid VTV roles."""
        if v is None:
            return v
        if v not in _VALID_ROLES:
            msg = f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}"
            raise ValueError(msg)
        return v
