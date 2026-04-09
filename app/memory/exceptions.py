"""Memory feature exceptions."""

from app.core.exceptions import NotFoundError


class MemoryNotFoundError(NotFoundError):
    """Raised when a memory entry is not found."""

    def __init__(self, memory_id: int) -> None:
        super().__init__(f"Memory entry {memory_id} not found")
