"""Multi-tier model routing for the VTV agent.

Classifies user prompts into fast/standard/complex tiers using
keyword and pattern matching. Zero latency overhead - no LLM calls.
"""

import re
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

ModelTier = Literal["fast", "standard", "complex"]

# --- Fast tier patterns ---
# Simple lookups, single-entity queries, status checks
_FAST_PATTERNS: list[re.Pattern[str]] = [
    # Status queries (LV: "kuri marsruti kavejas", "vai ir kavejas")
    # No trailing \b — stems match suffixed forms (kavējas, delayed)
    re.compile(r"\b(delay|kavēj|kavej|on.?time|laik[aā])", re.IGNORECASE),
    # Simple schedule lookups
    re.compile(
        r"\b(next bus|nakosais|nakošais|show schedule|paradiet grafiku|paradiet grafiku)\b",
        re.IGNORECASE,
    ),
    # Single entity lookups
    re.compile(r"\b(route \d+|marsrut[saua]?\s*\d+|maršrut[saūā]?\s*\d+)\b", re.IGNORECASE),
    # Stop queries
    re.compile(r"\b(stop|pietura|pieturā)\b", re.IGNORECASE),
    # Simple yes/no questions
    re.compile(r"^(is|vai|are|does|cik)\b", re.IGNORECASE),
    # Status/count queries
    re.compile(r"\b(how many|cik|count|status|statuss)\b", re.IGNORECASE),
    # Single driver/vehicle lookup
    re.compile(
        r"\b(driver|vaditaj|vadītāj|vehicle|transportlidzekl|transportlīdzekl)\b", re.IGNORECASE
    ),
]

# --- Complex tier patterns ---
# Multi-step analysis, bulk operations, optimization, cross-domain correlation
_COMPLEX_PATTERNS: list[re.Pattern[str]] = [
    # Analytical queries (no trailing \b — stems match suffixed forms)
    re.compile(r"\b(analyze|analyz|analize|analizē|compare|salidzin|salīdzin)", re.IGNORECASE),
    # Optimization requests
    re.compile(r"\b(optimize|optimiz|optimizē|improve|uzlabo|suggest|ieteik)", re.IGNORECASE),
    # Bulk/batch operations
    re.compile(
        r"\b(all routes|all stops|all drivers|visi marsrut|visi maršrut|visas pietura)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(bulk|batch|multiple|vairak|vairāk)\b", re.IGNORECASE),
    # Cross-domain correlation (no trailing \b — stems match plurals: trends, patterns)
    re.compile(r"\b(correlation|trend|pattern|tendenc|sakarib|sakarīb)", re.IGNORECASE),
    # Report generation
    re.compile(r"\b(report|parskats|pārskats|summary|kopsavilkum)\b", re.IGNORECASE),
    # Planning and scheduling
    re.compile(r"\b(plan|planot|plānot|reschedule|reorganize)\b", re.IGNORECASE),
    # Complex vault operations
    re.compile(r"\b(reorganize|restructure|migrate|move all|delete all)\b", re.IGNORECASE),
]


def classify_prompt(prompt: str) -> ModelTier:
    """Classify a user prompt into a model routing tier.

    Uses keyword and pattern matching to determine query complexity.
    Fast patterns are checked first (most queries are simple lookups).
    Complex patterns are checked second. Default is "standard".

    The classification is deliberately conservative:
    - Short prompts (< 20 chars) go to fast tier (likely simple commands)
    - Multiple complex pattern matches reinforce complex classification
    - Single complex match with fast matches defaults to standard

    Args:
        prompt: The user's message text.

    Returns:
        "fast", "standard", or "complex" tier classification.
    """
    prompt_stripped = prompt.strip()

    # Very short prompts are almost always simple lookups
    if len(prompt_stripped) < 20:
        return "fast"

    fast_matches = sum(1 for p in _FAST_PATTERNS if p.search(prompt_stripped))
    complex_matches = sum(1 for p in _COMPLEX_PATTERNS if p.search(prompt_stripped))

    # Complex wins when it has clear signal
    if complex_matches >= 2:
        return "complex"
    if complex_matches >= 1 and fast_matches == 0:
        return "complex"

    # Fast wins when it has signal and no complex signal
    if fast_matches >= 1 and complex_matches == 0:
        return "fast"

    # Mixed signals or no matches -> standard
    return "standard"
