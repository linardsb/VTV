"""Pydantic response schemas for Obsidian vault tool outputs.

These models define the structured data returned by Obsidian tools
(query_vault, manage_notes, manage_folders, bulk_operations).
The agent receives JSON-serialized versions of these models.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VaultResultConcise(BaseModel):
    """Concise search result for token efficiency."""

    model_config = ConfigDict(strict=True)

    path: str
    title: str
    modified: str


class VaultResultDetailed(BaseModel):
    """Detailed search result with metadata."""

    model_config = ConfigDict(strict=True)

    path: str
    title: str
    modified: str
    created: str | None = None
    size_bytes: int | None = None
    word_count: int | None = None
    tags: list[str] = []
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None
    snippet: str | None = None


class VaultSearchResponse(BaseModel):
    """Response from obsidian_query_vault."""

    model_config = ConfigDict(strict=True)

    count: int
    results: list[VaultResultConcise | VaultResultDetailed]
    truncated: bool = False
    hint: str | None = None


class NoteContent(BaseModel):
    """Response from reading a note."""

    model_config = ConfigDict(strict=True)

    path: str
    title: str
    content: str
    frontmatter: dict[str, str | list[str] | int | float | bool | None] | None = None
    word_count: int


class NoteOperationResult(BaseModel):
    """Response from create/update/delete/move operations."""

    model_config = ConfigDict(strict=True)

    success: bool
    action: str
    path: str
    message: str


class FolderEntry(BaseModel):
    """A file or folder entry in a directory listing."""

    model_config = ConfigDict(strict=True)

    name: str
    type: str  # "file" | "folder"
    modified: str | None = None
    size_bytes: int | None = None
    item_count: int | None = None
    children: list[FolderEntry] | None = None


class FolderListResponse(BaseModel):
    """Response from folder list operation."""

    model_config = ConfigDict(strict=True)

    path: str
    children: list[FolderEntry]
    total_files: int
    total_folders: int


class FolderOperationResult(BaseModel):
    """Response from folder create/delete/move operations."""

    model_config = ConfigDict(strict=True)

    success: bool
    action: str
    path: str
    message: str


class BulkOperationResult(BaseModel):
    """Response from bulk operations."""

    model_config = ConfigDict(strict=True)

    dry_run: bool
    action: str
    matched: int
    succeeded: int = 0
    failed: int = 0
    failures: list[dict[str, str]] = []
    preview: list[dict[str, str]] | None = None
    hint: str | None = None


class VaultError(BaseModel):
    """Actionable error response for agent consumption."""

    model_config = ConfigDict(strict=True)

    error: bool = True
    code: str
    message: str
    suggestion: str | None = None
    available_matches: list[str] | None = None
