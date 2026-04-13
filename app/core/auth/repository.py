"""Data access layer for dispatcher assignments."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import DispatcherAssignment
from app.core.logging import get_logger

logger = get_logger(__name__)


class AssignmentRepository:
    """Database operations for dispatcher route assignments."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def list_by_user(self, user_id: int) -> list[DispatcherAssignment]:
        """List all assignments for a user.

        Args:
            user_id: The user's database ID.

        Returns:
            List of DispatcherAssignment instances.
        """
        result = await self.db.execute(
            select(DispatcherAssignment)
            .where(DispatcherAssignment.user_id == user_id)
            .order_by(DispatcherAssignment.route_id)
        )
        return list(result.scalars().all())

    async def get(self, assignment_id: int) -> DispatcherAssignment | None:
        """Get a single assignment by ID.

        Args:
            assignment_id: The assignment's database ID.

        Returns:
            DispatcherAssignment instance or None.
        """
        result = await self.db.execute(
            select(DispatcherAssignment).where(DispatcherAssignment.id == assignment_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, route_id: int, assigned_by: int) -> DispatcherAssignment:
        """Create a single assignment.

        Args:
            user_id: The dispatcher user's ID.
            route_id: The route ID to assign.
            assigned_by: The admin user's ID who created the assignment.

        Returns:
            The newly created DispatcherAssignment.
        """
        assignment = DispatcherAssignment(
            user_id=user_id, route_id=route_id, assigned_by=assigned_by
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        logger.info(
            "rbac.assignment.create_completed",
            user_id=user_id,
            route_id=route_id,
            assigned_by=assigned_by,
        )
        return assignment

    async def delete(self, assignment: DispatcherAssignment) -> None:
        """Delete a single assignment.

        Args:
            assignment: The assignment to delete.
        """
        logger.info(
            "rbac.assignment.delete_completed",
            assignment_id=assignment.id,
            user_id=assignment.user_id,
            route_id=assignment.route_id,
        )
        await self.db.delete(assignment)
        await self.db.commit()

    async def bulk_replace(
        self, user_id: int, route_ids: list[int], assigned_by: int
    ) -> list[DispatcherAssignment]:
        """Replace all assignments for a user with a new set.

        Args:
            user_id: The dispatcher user's ID.
            route_ids: New set of route IDs to assign.
            assigned_by: The admin user's ID.

        Returns:
            List of newly created DispatcherAssignment instances.
        """
        await self.db.execute(
            delete(DispatcherAssignment).where(DispatcherAssignment.user_id == user_id)
        )
        assignments: list[DispatcherAssignment] = []
        for route_id in route_ids:
            assignment = DispatcherAssignment(
                user_id=user_id, route_id=route_id, assigned_by=assigned_by
            )
            self.db.add(assignment)
            assignments.append(assignment)
        await self.db.commit()
        for a in assignments:
            await self.db.refresh(a)
        logger.info(
            "rbac.assignment.bulk_replace_completed",
            user_id=user_id,
            route_count=len(route_ids),
            assigned_by=assigned_by,
        )
        return assignments
