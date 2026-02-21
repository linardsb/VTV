"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Successful login response — returned to frontend auth.ts."""

    id: int
    email: str
    name: str
    role: str


class UserResponse(BaseModel):
    """Public user information."""

    id: int
    email: str
    name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
