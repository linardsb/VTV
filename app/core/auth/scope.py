"""RBAC request scope resolution for dispatcher-scoped query filtering."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RequestScope:
    """Resolved RBAC scope for the current request.

    Attributes:
        user_id: The authenticated user's database ID.
        role: The user's role string.
        route_ids: Frozenset of allowed route IDs for dispatchers,
            or None for unrestricted access (admin/editor/viewer).
    """

    user_id: int
    role: str
    route_ids: frozenset[int] | None  # None = unrestricted

    @property
    def is_unrestricted(self) -> bool:
        """Return True if the user has unrestricted data access."""
        return self.route_ids is None


async def get_request_scope(
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RequestScope:
    """Resolve RBAC scope from user role and dispatcher assignments.

    Args:
        current_user: The authenticated user.
        db: Database session for loading assignments.

    Returns:
        RequestScope with route_ids=None for unrestricted roles,
        or a frozenset of assigned route IDs for dispatchers.
    """
    if current_user.role != "dispatcher":
        logger.info(
            "rbac.scope.resolved",
            user_id=current_user.id,
            role=current_user.role,
            scope="unrestricted",
        )
        return RequestScope(
            user_id=current_user.id,
            role=current_user.role,
            route_ids=None,
        )

    # Dispatcher: load assignments
    from app.core.auth.models import DispatcherAssignment

    result = await db.execute(
        select(DispatcherAssignment.route_id).where(DispatcherAssignment.user_id == current_user.id)
    )
    route_ids = frozenset(row[0] for row in result.all())
    logger.info(
        "rbac.scope.resolved",
        user_id=current_user.id,
        role="dispatcher",
        route_count=len(route_ids),
    )
    return RequestScope(
        user_id=current_user.id,
        role=current_user.role,
        route_ids=route_ids,
    )
