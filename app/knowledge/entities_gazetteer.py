"""Entity gazetteer + normalization helpers for KB-5.

Loads transit stop names from the ``stops`` table into a module-level
case-folded frozenset at startup so the regex/gazetteer extractor can
match them in document and query text without per-call DB lookups.

Also exposes bounded regex patterns for route numbers (``Maršruts 22``,
``Route 22``) and EU transport regulations (``EU 561/2006``). Patterns
use bounded quantifiers to avoid ReDoS (CTX-INPUT): the digit groups
are capped and the ``\\w*`` after ``maršrut`` is bounded to 20 chars
so adversarial input cannot drive runaway backtracking.
"""

from __future__ import annotations

import re

from sqlalchemy import select

from app.core.database import get_db_context
from app.core.logging import get_logger
from app.stops.models import Stop

logger = get_logger(__name__)

# Bounded quantifiers protect against ReDoS even though input is clipped.
_ROUTE_RE = re.compile(
    r"(?:maršrut\w{0,20}|route)\s+(\d{1,4}[A-Za-z]?)",
    re.IGNORECASE,
)
_REGULATION_RE = re.compile(
    r"(?:EU|ES|Regulation|Regula)\s+(\d{1,4}/\d{2,4})",
    re.IGNORECASE,
)

# Maximum input length passed to regex/gazetteer matching (CTX-INPUT).
MAX_INPUT_CHARS = 20_000

# Internal gazetteer state — module singleton loaded via ``load_stop_gazetteer``.
_stop_names_lower: frozenset[str] | None = None


async def load_stop_gazetteer() -> None:
    """Load ``Stop.stop_name`` rows into a case-folded frozenset.

    Called once at application startup (or re-called explicitly to refresh
    after GTFS import). The in-memory footprint is bounded by the real stop
    count (~2000 rows for Riga, ~50 KB) so holding it as a module-level
    frozenset is safe.
    """
    global _stop_names_lower
    async with get_db_context() as session:
        result = await session.execute(select(Stop.stop_name))
        names = {row[0].casefold() for row in result.all() if row[0]}
    _stop_names_lower = frozenset(names)
    logger.info("knowledge.gazetteer.loaded", count=len(names))


def get_stop_names() -> frozenset[str]:
    """Return the loaded stop-name set or an empty set if not yet loaded."""
    return _stop_names_lower if _stop_names_lower is not None else frozenset()


def reset_gazetteer() -> None:
    """Clear the in-memory gazetteer — test-only helper."""
    global _stop_names_lower
    _stop_names_lower = None


def set_gazetteer(names: frozenset[str]) -> None:
    """Directly seed the gazetteer — test-only helper."""
    global _stop_names_lower
    _stop_names_lower = names


def normalize_route(raw_match: str) -> str:
    """Normalize a raw route-match string to ``route_<lowercased-number>``.

    Accepts the full matched substring (e.g. ``"Maršruts 22"``) and extracts
    the trailing number via :data:`_ROUTE_RE`. Falls back to a lower-cased
    copy of ``raw_match`` when the regex cannot find a number (defensive —
    shouldn't happen since we only call this on regex matches).
    """
    match = _ROUTE_RE.search(raw_match)
    if match is None:
        return raw_match.lower()
    return f"route_{match.group(1).lower()}"


def normalize_stop(raw: str) -> str:
    """Casefold and trim a stop name for canonical form."""
    return raw.casefold().strip()


def normalize_regulation(raw_match: str) -> str:
    """Normalize a raw regulation-match string to ``reg_<number>/<year>``."""
    match = _REGULATION_RE.search(raw_match)
    if match is None:
        return raw_match.lower()
    return f"reg_{match.group(1)}"
