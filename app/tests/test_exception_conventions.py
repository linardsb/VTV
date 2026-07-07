"""Convention tests for exception usage in route files.

VTV mandates that route handlers raise ``AppError`` subclasses (mapped to HTTP
status codes via ``app_exception_handler``) instead of raw ``HTTPException``.
Three categories are exempt and tracked in an explicit allowlist:

- Auth-flow refresh failures that share the auth/dependencies 401 contract
  (``WWW-Authenticate``-shaped semantics, separate handlers).
- Custom 429 responses from the agent chat quota tracker — no ``AppError``
  subclass exists for that status today.
- Webhook auth checks (fleet) that are not user-JWT auth and intentionally
  bypass the global handler chain pending a webhook-hardening pass.

Adding new exempt sites must be a deliberate, reviewed change: bump the
allowlist below and explain the reason in the comment next to the entry.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Each entry: (relative path under app/, expected raw-HTTPException raise count, reason).
# The test fails if a file's count drifts from the expected value, in either
# direction, so deletions force a maintainer to update the allowlist.
ROUTE_HTTPEXCEPTION_ALLOWLIST: dict[str, tuple[int, str]] = {
    "auth/routes.py": (
        1,
        "L68 refresh-token 401 — auth-flow contract (parallel to auth/dependencies)",
    ),
    "core/agents/routes.py": (
        1,
        "L66 daily quota 429 — no AppError subclass for 429 today",
    ),
    "fleet/routes.py": (
        2,
        "L47/L50 webhook token check — pending webhook-hardening refactor",
    ),
}

APP_DIR = Path(__file__).resolve().parents[1]


def _count_raw_httpexception_raises(file_path: Path) -> int:
    """AST-count direct ``raise HTTPException(...)`` nodes in a route file.

    Args:
        file_path: Absolute path to a Python source file.

    Returns:
        Number of ``Raise`` nodes whose ``exc`` is ``HTTPException(...)``.
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        target = node.exc
        if isinstance(target, ast.Call):
            target = target.func
        name = target.id if isinstance(target, ast.Name) else None
        if name == "HTTPException":
            count += 1
    return count


def _iter_route_files() -> list[Path]:
    """Yield every ``routes.py`` under ``app/`` (excluding tests)."""
    return sorted(p for p in APP_DIR.rglob("routes.py") if "tests" not in p.parts)


def test_no_unexpected_raw_httpexception_in_routes() -> None:
    """Every route file matches the allowlist exactly — no drift allowed.

    A file appearing in the allowlist with an outdated count signals either
    a regression (someone added a new raw raise) or a successful migration
    that forgot to shrink the allowlist. A file NOT in the allowlist with a
    nonzero count is always a regression.
    """
    findings: dict[str, int] = {}
    for path in _iter_route_files():
        count = _count_raw_httpexception_raises(path)
        if count == 0:
            continue
        rel = path.relative_to(APP_DIR).as_posix()
        findings[rel] = count

    expected = {rel: count for rel, (count, _) in ROUTE_HTTPEXCEPTION_ALLOWLIST.items()}
    assert findings == expected, (
        f"Raw HTTPException raises in routes.py drifted from allowlist.\n"
        f"  Found:    {findings}\n"
        f"  Expected: {expected}\n"
        f"Migrate raw HTTPException to AppError subclasses (BadRequestError, "
        f"DomainValidationError, NotFoundError, ConflictError, PayloadTooLargeError, "
        f"UnsupportedMediaTypeError, ServiceUnavailableError) — see app/core/exceptions.py. "
        f"Update ROUTE_HTTPEXCEPTION_ALLOWLIST only after maintainer review."
    )


def test_allowlisted_files_exist() -> None:
    """Every allowlist entry must point to a real route file.

    Prevents the allowlist from rotting silently after a feature is renamed
    or removed.
    """
    missing = [rel for rel in ROUTE_HTTPEXCEPTION_ALLOWLIST if not (APP_DIR / rel).is_file()]
    assert not missing, f"Allowlist references nonexistent files: {missing}"
