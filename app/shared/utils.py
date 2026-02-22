"""Shared utility functions."""

from datetime import UTC, datetime


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcard characters.

    Args:
        value: Raw search string that may contain %, _, or \\ characters.

    Returns:
        Escaped string safe for use in LIKE/ILIKE queries.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def utcnow() -> datetime:
    """Get current UTC time with timezone information.

    Returns timezone-aware datetime in UTC. This should be used
    instead of datetime.utcnow() which returns naive datetimes.

    Returns:
        datetime: Current UTC time with timezone information.

    Example:
        now = utcnow()
        print(now.isoformat())  # 2025-10-29T14:30:00+00:00
    """
    return datetime.now(UTC)


def format_iso(dt: datetime) -> str:
    """Format datetime as ISO 8601 string.

    Args:
        dt: Datetime object to format.

    Returns:
        str: ISO 8601 formatted string.

    Example:
        now = utcnow()
        iso_string = format_iso(now)
        print(iso_string)  # 2025-10-29T14:30:00+00:00
    """
    return dt.isoformat()
