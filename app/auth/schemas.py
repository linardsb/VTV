"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr


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


class UserResponse(BaseModel):
    """Public user information."""

    id: int
    email: str
    name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
