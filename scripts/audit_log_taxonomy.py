# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
"""Audit structured log events against docs/logging-standard.md taxonomy.

Scans all Python files under app/ (excluding tests/) for logger.* calls,
extracts event names, and compares them against the documented taxonomy.
Reports undocumented events (in code but not in taxonomy) and stale events
(in taxonomy but not in code).

Usage:
    uv run python scripts/audit_log_taxonomy.py
    uv run python scripts/audit_log_taxonomy.py --verbose
    uv run python scripts/audit_log_taxonomy.py --ignore-patterns crud
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"
TAXONOMY_FILE = PROJECT_ROOT / "docs" / "logging-standard.md"

# Events from docstrings, examples, and test helpers -- not real production events
EXAMPLE_EVENT_PREFIXES = (
    "test.",
    "user.",
    "product.",
    "order.",
    "process.",
    "notification.",
    "input.",
    "operation.",
)

# Standard CRUD and lifecycle patterns that are intentionally not individually
# documented. These follow {feature}.{entity}.{action}_{state} convention.
CRUD_ACTIONS = {
    # Basic CRUD
    "fetch_started",
    "fetch_completed",
    "fetch_failed",
    "list_started",
    "list_completed",
    "list_all_started",
    "list_all_completed",
    "create_started",
    "create_completed",
    "create_failed",
    "update_started",
    "update_completed",
    "update_failed",
    "delete_started",
    "delete_completed",
    "delete_failed",
    # Extended CRUD actions
    "seed_started",
    "seed_completed",
    "seed_skipped",
    "list_by_driver_started",
    "acknowledge_started",
    "acknowledge_completed",
    "acknowledge_failed",
    "resolve_started",
    "resolve_completed",
    "resolve_failed",
    # Auth-specific
    "login_started",
    "login_completed",
    "login_failed",
    "logout_started",
    "logout_completed",
}

# Feature domains whose CRUD events follow the standard pattern
CRUD_DOMAINS = {
    "alerts",
    "drivers",
    "events",
    "fleet",
    "geofences",
    "schedules",
    "skills",
    "stops",
    "vehicles",
    "knowledge",
    "analytics",
    "compliance",
    "public_api",
    "auth",
    "memory",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit structured log events against taxonomy doc.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show file:line for each event",
    )
    parser.add_argument(
        "--ignore-patterns",
        nargs="*",
        default=["crud", "examples", "evals", "feature"],
        help="Ignore pattern sets: crud, examples, evals, feature (default: all four)",
    )
    parser.add_argument(
        "--show-stale",
        action="store_true",
        help="Show stale events (documented but not in code)",
    )
    return parser.parse_args()


def extract_taxonomy_events(taxonomy_path: Path) -> set[str]:
    """Parse documented event names from taxonomy tree blocks in markdown.

    Handles both box-drawing (e.g. +-- event_name) and Unicode tree chars.
    Tracks parent prefix from lines like 'agent.' or 'transit.' and composes
    full event names from nested tree entries.
    """
    content = taxonomy_path.read_text()
    events: set[str] = set()

    in_code_block = False
    parent_stack: list[str] = []  # stack of domain prefixes

    # Box-drawing and tree prefix characters to strip
    tree_prefix_re = re.compile(r"^[\s│├└─|+\-]*")

    for line in content.splitlines():
        stripped = line.strip()

        # Track code fence boundaries
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if not in_code_block:
                parent_stack.clear()
            continue

        if not in_code_block:
            continue

        # Strip tree-drawing prefix to get the actual content
        content_part = tree_prefix_re.sub("", stripped)
        if not content_part:
            continue

        # Check if line had tree-drawing prefix (indicates nesting)
        has_tree_prefix = stripped != content_part

        # Measure tree depth by finding the column position of the first
        # branch character (├ or └). This handles both "│   ├──" (pipe indent)
        # and "    ├──" (space indent under last child).
        branch_match = re.search(r"[├└]", line)
        depth = branch_match.start() // 4 if branch_match else 0

        # Parent domain line: "agent." or "transit." etc.
        parent_match = re.match(r"^(\w[\w.]*)\.\s*(?:#.*)?$", content_part)
        if parent_match:
            name = parent_match.group(1)
            if not has_tree_prefix or not parent_stack:
                # Top-level domain (no tree prefix = bare "agent." line)
                parent_stack = [name + "."]
            else:
                # Nested sub-domain (has tree prefix = "├── tool." under "agent.")
                # Trim stack to current depth + 1
                trim_to = min(depth + 1, len(parent_stack))
                parent_stack = parent_stack[:trim_to]
                parent_stack.append(parent_stack[-1] + name + ".")
            continue

        # Event line: "event_name  # comment" or "lifecycle.started  # comment"
        # Must be a valid identifier (word chars + dots), not a Python keyword
        event_match = re.match(r"^(\w[\w.]*\w)\s*(?:#.*)?$", content_part)
        if event_match:
            event_name = event_match.group(1)
            # Skip Python keywords that appear in code examples
            if event_name in {"raise", "return", "except", "import", "from", "pass"}:
                continue
            # Determine the correct parent based on depth
            if parent_stack:
                parent_idx = min(depth + 1, len(parent_stack)) - 1
                parent_idx = max(0, parent_idx)
                full_event = parent_stack[parent_idx] + event_name
            else:
                full_event = event_name
            events.add(full_event)

    return events


def extract_code_events(
    app_dir: Path,
) -> dict[str, list[str]]:
    """Extract log event names from Python source files.

    Returns a dict mapping event_name -> list of "file:line" locations.
    Handles multiline logger calls by reading entire file content.
    """
    event_locations: dict[str, list[str]] = {}

    # Pattern matches logger.info("event.name", ...) including multiline
    event_pattern = re.compile(
        r'logger\.(?:info|warning|error|debug|critical)\(\s*"([^"]+)"',
    )

    for py_file in app_dir.rglob("*.py"):
        # Skip test directories
        parts = py_file.relative_to(app_dir).parts
        if "tests" in parts or "__pycache__" in parts:
            continue

        try:
            content = py_file.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        # Find all event names
        for match in event_pattern.finditer(content):
            event_name = match.group(1)

            # Must look like a dotted namespace (at least domain.action)
            if "." not in event_name:
                continue

            # Calculate line number from match position
            line_num = content[: match.start()].count("\n") + 1
            rel_path = py_file.relative_to(app_dir.parent)
            location = f"{rel_path}:{line_num}"

            if event_name not in event_locations:
                event_locations[event_name] = []
            event_locations[event_name].append(location)

    return event_locations


def _is_example_event(event: str) -> bool:
    """Check if event is from example/docstring code."""
    return any(event.startswith(prefix) for prefix in EXAMPLE_EVENT_PREFIXES)


def _is_crud_event(event: str) -> bool:
    """Check if event follows standard CRUD pattern for a known domain."""
    parts = event.split(".")
    if len(parts) < 2:
        return False
    domain = parts[0]
    action = parts[-1]
    # Check compound actions like list_all_started
    if len(parts) >= 3:
        action = parts[-1]
        compound = parts[-2] + "_" + parts[-1]
        if domain in CRUD_DOMAINS and (action in CRUD_ACTIONS or compound in CRUD_ACTIONS):
            return True
    return domain in CRUD_DOMAINS and action in CRUD_ACTIONS


def _is_eval_event(event: str) -> bool:
    """Check if event is from the evals subsystem (dev/test tooling)."""
    return ".evals." in event


# Infrastructure domains that MUST be documented in the taxonomy.
# Everything else is a "feature domain" whose events follow standard patterns.
INFRASTRUCTURE_DOMAINS = {
    "agent",
    "application",
    "database",
    "health",
    "request",
    "external",
    "shutdown",
    "jobs",
    "cache",
    "redis",
    "resilience",
    "security",
    "rate_limit",
    "rbac",
    "anomaly",
    "app",
    "transit",  # transit has its own infrastructure events (poller, ws, etc.)
    "memory",
}


def _is_feature_domain_event(event: str) -> bool:
    """Check if event is from a feature domain (not infrastructure).

    Feature domains follow standard naming patterns and don't need individual
    taxonomy entries. Infrastructure domains must be explicitly documented.
    """
    domain = event.split(".")[0]
    return domain not in INFRASTRUCTURE_DOMAINS


def main() -> int:
    args = _parse_args()

    if not TAXONOMY_FILE.exists():
        print(f"[audit] ERROR: Taxonomy file not found: {TAXONOMY_FILE}")
        return 1

    if not APP_DIR.exists():
        print(f"[audit] ERROR: App directory not found: {APP_DIR}")
        return 1

    # Extract events from both sources
    taxonomy_events = extract_taxonomy_events(TAXONOMY_FILE)
    code_event_locations = extract_code_events(APP_DIR)
    code_events = set(code_event_locations.keys())

    ignore_flags = set(args.ignore_patterns or [])

    # Filter out ignorable events
    filtered_code_events = set()
    ignored_count = 0
    for event in code_events:
        skip = False
        if "examples" in ignore_flags and _is_example_event(event):
            skip = True
        if "crud" in ignore_flags and _is_crud_event(event):
            skip = True
        if "evals" in ignore_flags and _is_eval_event(event):
            skip = True
        if "feature" in ignore_flags and _is_feature_domain_event(event):
            skip = True
        if skip:
            ignored_count += 1
        else:
            filtered_code_events.add(event)

    undocumented = sorted(filtered_code_events - taxonomy_events)
    stale = sorted(taxonomy_events - code_events)

    # Report
    print(f"[audit] Taxonomy events: {len(taxonomy_events)}")
    print(f"[audit] Code events: {len(code_events)} ({ignored_count} ignored)")
    print(f"[audit] Undocumented: {len(undocumented)}")
    print(f"[audit] Stale: {len(stale)}")
    print()

    if undocumented:
        print("=== UNDOCUMENTED EVENTS (in code, not in taxonomy) ===")
        # Group by domain
        by_domain: dict[str, list[str]] = {}
        for event in undocumented:
            domain = event.split(".")[0]
            by_domain.setdefault(domain, []).append(event)

        for domain in sorted(by_domain.keys()):
            print(f"\n  [{domain}]")
            for event in by_domain[domain]:
                if args.verbose and event in code_event_locations:
                    locations = code_event_locations[event]
                    print(f"    {event}")
                    for loc in locations[:3]:  # Show max 3 locations
                        print(f"      -> {loc}")
                else:
                    print(f"    {event}")

    if args.show_stale and stale:
        print("\n=== STALE EVENTS (in taxonomy, not in code) ===")
        for event in stale:
            print(f"    {event}")

    if not undocumented:
        print("[audit] OK: All code events are documented in taxonomy.")
        return 0

    print(f"\n[audit] FAIL: {len(undocumented)} undocumented event(s) found.")
    print("[audit] Add them to docs/logging-standard.md or extend --ignore-patterns.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
