"""Database repository for user operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class UserRepository:
    """Handles all database operations for User model."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_email(self, email: str) -> User | None:
        """Find a user by email address."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_by_id(self, user_id: int) -> User | None:
        """Find a user by database ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        """Create a new user."""
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """Update an existing user (e.g., failed_attempts, locked_until)."""
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """Delete a user entity from the database."""
        await self.db.delete(user)
        await self.db.flush()

    async def count(self) -> int:
        """Count total users."""
        from sqlalchemy import func

        result = await self.db.execute(select(func.count()).select_from(User))
        return result.scalar_one()
