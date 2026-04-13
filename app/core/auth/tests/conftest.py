"""Shared test fixtures for core auth RBAC tests."""

from app.core.auth.scope import RequestScope


def make_scope(
    *, role: str = "admin", route_ids: frozenset[int] | None = None, user_id: int = 1
) -> RequestScope:
    """Factory to create a RequestScope with sensible defaults.

    Args:
        role: User role string.
        route_ids: Frozenset of allowed route IDs, or None for unrestricted.
        user_id: The user's database ID.

    Returns:
        A RequestScope instance.
    """
    return RequestScope(user_id=user_id, role=role, route_ids=route_ids)
