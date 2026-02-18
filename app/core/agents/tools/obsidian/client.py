"""HTTP client wrapper for the Obsidian Local REST API.

Encapsulates auth, SSL, error handling, and path sandboxing for all
vault operations. Used by all 4 Obsidian tools.
"""

from __future__ import annotations

import time

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


def _validate_path(path: str) -> str:
    """Sanitize and validate vault path.

    Args:
        path: Relative path within the vault.

    Returns:
        Cleaned path string.

    Raises:
        ValueError: If path contains directory traversal.
    """
    if ".." in path:
        msg = f"Path traversal not allowed: '{path}'"
        raise ValueError(msg)
    return path.lstrip("/")


class ObsidianClient:
    """Async HTTP client for the Obsidian Local REST API.

    Wraps httpx.AsyncClient to provide typed methods for vault operations
    with path validation, structured logging, and error handling.

    Args:
        http_client: Pre-configured async HTTP client (with auth headers and SSL disabled).
        vault_url: Base URL for the Obsidian Local REST API.
    """

    def __init__(self, http_client: httpx.AsyncClient, vault_url: str) -> None:
        self._http_client = http_client
        self._vault_url = vault_url.rstrip("/")

    async def search(
        self, query: str, path: str | None = None
    ) -> list[dict[str, str | int | float | None]]:
        """Full-text search via POST /search/simple/.

        Args:
            query: Search text.
            path: Optional folder scope for search.

        Returns:
            List of search result dicts with filename, score, and matches.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status.
            httpx.ConnectError: If the vault API is unreachable.
        """
        start = time.monotonic()
        url = f"{self._vault_url}/search/simple/"
        logger.info("obsidian.client.request_started", method="POST", path="/search/simple/")

        params: dict[str, str] = {}
        if path:
            params["contextLength"] = "100"

        response = await self._http_client.post(
            url, content=query, headers={"Content-Type": "text/plain"}
        )
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "obsidian.client.request_completed",
            method="POST",
            path="/search/simple/",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        results: list[dict[str, str | int | float | None]] = response.json()
        return results

    async def get_note(self, filepath: str) -> str:
        """Read note content via GET /vault/{filepath}.

        Args:
            filepath: Relative path to the note within the vault.

        Returns:
            Raw markdown content of the note.

        Raises:
            httpx.HTTPStatusError: If note not found (404) or other error.
            httpx.ConnectError: If the vault API is unreachable.
        """
        clean_path = _validate_path(filepath)
        start = time.monotonic()
        url = f"{self._vault_url}/vault/{clean_path}"
        logger.info("obsidian.client.request_started", method="GET", path=f"/vault/{clean_path}")

        response = await self._http_client.get(url)
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "obsidian.client.request_completed",
            method="GET",
            path=f"/vault/{clean_path}",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response.text

    async def put_note(self, filepath: str, content: str) -> None:
        """Create or overwrite note via PUT /vault/{filepath}.

        Args:
            filepath: Relative path for the note.
            content: Full markdown content to write.

        Raises:
            httpx.HTTPStatusError: If the API returns an error.
            httpx.ConnectError: If the vault API is unreachable.
        """
        clean_path = _validate_path(filepath)
        start = time.monotonic()
        url = f"{self._vault_url}/vault/{clean_path}"
        logger.info("obsidian.client.request_started", method="PUT", path=f"/vault/{clean_path}")

        response = await self._http_client.put(
            url, content=content, headers={"Content-Type": "text/markdown"}
        )
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "obsidian.client.request_completed",
            method="PUT",
            path=f"/vault/{clean_path}",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

    async def patch_note(self, filepath: str, content: str, mode: str = "append") -> None:
        """Partial update via PATCH /vault/{filepath}.

        Args:
            filepath: Relative path to the note.
            content: Content to insert.
            mode: Insertion mode - "append" or "prepend".

        Raises:
            httpx.HTTPStatusError: If the API returns an error.
            httpx.ConnectError: If the vault API is unreachable.
        """
        clean_path = _validate_path(filepath)
        start = time.monotonic()
        url = f"{self._vault_url}/vault/{clean_path}"
        logger.info("obsidian.client.request_started", method="PATCH", path=f"/vault/{clean_path}")

        headers: dict[str, str] = {"Content-Type": "text/markdown"}
        if mode == "prepend":
            headers["Content-Insertion-Position"] = "beginning"
        else:
            headers["Content-Insertion-Position"] = "end"

        response = await self._http_client.patch(url, content=content, headers=headers)
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "obsidian.client.request_completed",
            method="PATCH",
            path=f"/vault/{clean_path}",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

    async def delete_note(self, filepath: str) -> None:
        """Delete note via DELETE /vault/{filepath}.

        Args:
            filepath: Relative path to the note.

        Raises:
            httpx.HTTPStatusError: If the API returns an error.
            httpx.ConnectError: If the vault API is unreachable.
        """
        clean_path = _validate_path(filepath)
        start = time.monotonic()
        url = f"{self._vault_url}/vault/{clean_path}"
        logger.info("obsidian.client.request_started", method="DELETE", path=f"/vault/{clean_path}")

        response = await self._http_client.delete(url)
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "obsidian.client.request_completed",
            method="DELETE",
            path=f"/vault/{clean_path}",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

    async def list_directory(self, path: str = "/") -> list[dict[str, str | int | None]]:
        """List directory contents via GET /vault/ with Accept: application/json.

        Args:
            path: Relative folder path within the vault.

        Returns:
            List of file/folder entry dicts.

        Raises:
            httpx.HTTPStatusError: If the API returns an error.
            httpx.ConnectError: If the vault API is unreachable.
        """
        clean_path = _validate_path(path) if path != "/" else ""
        start = time.monotonic()
        url = f"{self._vault_url}/vault/{clean_path}"
        logger.info("obsidian.client.request_started", method="GET", path=f"/vault/{clean_path}")

        response = await self._http_client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "obsidian.client.request_completed",
            method="GET",
            path=f"/vault/{clean_path}",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        result: list[dict[str, str | int | None]] = response.json()
        return result
