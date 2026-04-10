"""Response validation for transit agent outputs.

Checks agent responses for plausibility issues (impossible route numbers,
unrealistic delays, missing diacritics, time consistency, citation
grounding, language match) and flags stale data usage.

AI-5.2 introduces severity-tagged ``Issue`` objects, an optional
``ValidationContext`` for cache- and tool-result-aware checks, and 6
extended QA checks (route/stop existence, time consistency, citation
grounding, language match, per-response stale-data inspection). Errors
flow through the AI-5.1 self-correction loop and trigger a retry;
warnings are footnote-only.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic_ai.messages import ModelMessage, ToolReturnPart

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.agents.tools.transit.static_cache import GTFSStaticCache

logger = get_logger(__name__)

# Module-level flag: set to a monotonic timestamp when the agent serves
# data from a stale cache (circuit breaker fallback). Reset to 0.0 when
# fresh data is successfully fetched.
last_stale_data_timestamp: float = 0.0

# Threshold in seconds for considering cached data "stale" in warnings.
_STALE_DATA_THRESHOLD: float = 300.0  # 5 minutes

# Maximum regex iterations per check — defends against pathological output.
_MAX_REGEX_ITERATIONS: int = 200

Severity = Literal["error", "warning"]

# Common Latvian words that should contain diacritics when written correctly.
# Maps the incorrectly-written form to the correct form.
_LATVIAN_DIACRITICS: dict[str, str] = {
    "iela": "iela",  # correct as-is, but check for missing diacritics in context
    "Rigas": "R\u012bgas",
    "marsruts": "mar\u0161ruts",
    "vilciens": "vilciens",
    "tramvajs": "tramvajs",
    "pieturas": "pieturas",
    "stacija": "stacija",
    "lidosta": "lidosta",
    "autobuss": "autobuss",
    # Words that are commonly missing diacritics
    "Satiksme": "Satiksme",
    "Brivibas": "Br\u012bv\u012bbas",
    "Caka": "\u010caka",
    "Gertrudes": "\u0122ertr\u016bdes",
    "Lacplesa": "L\u0101\u010dpl\u0113\u0161a",
    "Barona": "Baro\u0146a",
    "Dzirnavu": "Dzirnavu",
    "Terbatas": "T\u0113rbatas",
    "Valdemara": "Vald\u0113m\u0101ra",
    "Merkela": "Merke\u013ca",
    "Aspazijas": "Aspazijas",
    "Brivibas bulvaris": "Br\u012bv\u012bbas bulv\u0101ris",
}

# Regex for route numbers in context (e.g., "route 15", "maršruts 42", "#7")
_ROUTE_PATTERN = re.compile(
    r"(?:route|mar[sš]rut[sa]?|#|nr\.?\s*)\s*(\d+)",
    re.IGNORECASE,
)

# Regex for delay mentions (e.g., "5 minutes late", "delayed by 120 seconds")
_DELAY_PATTERN = re.compile(
    r"(\-?\d+(?:\.\d+)?)\s*(?:min[uū]t|minut|second|sekund)",
    re.IGNORECASE,
)

# Regex for stop names following "pietura" / "stop" anchor words.
_STOP_PATTERN = re.compile(
    r"(?:pietur[āai]|stop)\s+"
    r"([A-Z\u0100\u010c\u0112\u0122\u012a\u0136\u013b\u0145\u0160\u016a\u017d]"
    r"[\w\-\u0101\u010d\u0113\u0123\u012b\u0137\u013c\u0146\u0161\u016b\u017e]{2,40}"
    r"(?:\s+[A-Z\u0100\u010c\u0112\u0122\u012a\u0136\u013b\u0145\u0160\u016a\u017d]"
    r"[\w\-\u0101\u010d\u0113\u0123\u012b\u0137\u013c\u0146\u0161\u016b\u017e]{2,40})*)",
    re.IGNORECASE,
)

# Regex for HH:MM[:SS] timestamps.
_TIME_PATTERN = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")

# Regex for Markdown citations of the form `[title](/lv|/en/documents/{id})`.
_CITATION_PATTERN = re.compile(r"\[[^\]]+\]\(/(?:lv|en)/documents/(\d+)\)")

# English stopwords used by the cheap language detector.
_EN_STOPWORD_PATTERN = re.compile(
    r"\b(?:the|and|of|to|is|are|with|bus|route|stop|schedule)\b",
    re.IGNORECASE,
)

# Latvian-only diacritic characters used by the cheap language detector.
_LV_DIACRITIC_CHARS = frozenset(
    "\u0101\u010d\u0113\u0123\u012b\u0137\u013c\u0146\u0161\u016b\u017e"
    "\u0100\u010c\u0112\u0122\u012a\u0136\u013b\u0145\u0160\u016a\u017d"
)

# Transit tools whose JSON returns include a POSIX `timestamp` field.
_TRANSIT_TOOLS_WITH_TIMESTAMPS: tuple[str, ...] = (
    "query_bus_status",
    "get_route_schedule",
    "get_adherence_report",
)


@dataclass(frozen=True)
class Issue:
    """A single validation finding.

    Attributes:
        check_name: Stable identifier of the producing check
            (e.g. ``"route_existence"``). Used for metrics and tests.
        description: Human-readable message rendered in footnotes
            and corrective retry prompts.
        severity: ``"error"`` triggers a self-correction retry.
            ``"warning"`` is footnote-only and never retries.
    """

    check_name: str
    description: str
    severity: Severity


@dataclass
class ToolReturnRecord:
    """A parsed tool return extracted from agent message history.

    Attributes:
        tool_name: The name of the tool that produced this return.
        payload: Parsed JSON value (dict / list / scalar) when the
            tool returned a JSON-encoded string, otherwise the raw
            content object.
    """

    tool_name: str
    payload: Any


@dataclass
class ValidationContext:
    """Optional context passed into :func:`validate_transit_response`.

    All fields are optional. Checks that need a missing field
    gracefully skip themselves (no false errors).

    Attributes:
        user_message: The original end-user prompt — used by the
            language-match check.
        static_cache: A loaded ``GTFSStaticCache`` (or subclass).
            Typed as ``Any`` to avoid a runtime import cycle with
            ``app.core.agents.tools.transit.static_cache``.
        tool_returns: Parsed tool returns from
            ``result.all_messages()``.
    """

    user_message: str | None = None
    static_cache: Any | None = None
    tool_returns: list[ToolReturnRecord] = field(default_factory=lambda: list[ToolReturnRecord]())


@dataclass
class ValidationResult:
    """Result of validating a transit agent response.

    Attributes:
        is_valid: True if no issues were found.
        issues: All issues raised by the checks (errors + warnings).
        warnings: Derived view — ``[i.description for i in issues]``.
            Kept for backward compatibility with footnote rendering in
            ``service.py``.
        sanitized_response: The response text, potentially with
            annotations.
    """

    is_valid: bool = True
    issues: list[Issue] = field(default_factory=lambda: list[Issue]())
    warnings: list[str] = field(default_factory=lambda: list[str]())
    sanitized_response: str = ""


def extract_tool_returns(messages: list[ModelMessage]) -> list[ToolReturnRecord]:
    """Extract parsed tool returns from a Pydantic AI message history.

    Iterates ``messages`` looking for ``ToolReturnPart`` instances and
    records ``(tool_name, payload)`` pairs. JSON-encoded string content
    is parsed; anything else is recorded as-is. The whole function is
    wrapped in a try/except so a malformed message stream never blocks
    a dispatcher response.

    Args:
        messages: ``result.all_messages()`` from a pydantic_ai agent run.

    Returns:
        A list of :class:`ToolReturnRecord`. Empty on any failure.
    """
    records: list[ToolReturnRecord] = []
    try:
        for message in messages:
            parts = getattr(message, "parts", None)
            if parts is None:
                continue
            for part in parts:
                if not isinstance(part, ToolReturnPart):
                    continue
                content = part.content
                payload: Any = content
                if isinstance(content, str):
                    try:
                        payload = json.loads(content)
                    except (json.JSONDecodeError, ValueError):
                        payload = content
                records.append(ToolReturnRecord(tool_name=part.tool_name, payload=payload))
    except Exception:
        logger.error("agent.validation.extract_tool_returns_failed", exc_info=True)
        return []
    return records


def validate_transit_response(
    response: str,
    context: ValidationContext | None = None,
) -> ValidationResult:
    """Validate a transit agent response for plausibility issues.

    Runs all deterministic QA checks. Existence- and grounding-style
    checks gracefully no-op when their context dependency is missing.

    Args:
        response: The agent's text response to validate.
        context: Optional :class:`ValidationContext` carrying the user
            message, GTFS static cache, and parsed tool returns.

    Returns:
        :class:`ValidationResult` listing all issues found. ``is_valid``
        is ``False`` iff any issue was raised.
    """
    result = ValidationResult(sanitized_response=response)
    ctx = context or ValidationContext()

    _check_route_plausibility(response, result)
    _check_delay_plausibility(response, result)
    _check_stale_data(result, ctx)
    _check_latvian_diacritics(response, result)

    _check_route_existence(response, result, ctx)
    _check_stop_existence(response, result, ctx)
    _check_time_consistency(response, result)
    _check_citation_grounding(response, result, ctx)
    _check_language_match(response, result, ctx)

    result.warnings = [i.description for i in result.issues]
    result.is_valid = not result.issues
    return result


def _check_route_plausibility(response: str, result: ValidationResult) -> None:
    """Flag route numbers outside the plausible range 1-999."""
    for idx, match in enumerate(_ROUTE_PATTERN.finditer(response)):
        if idx >= _MAX_REGEX_ITERATIONS:
            break
        try:
            route_num = int(match.group(1))
        except ValueError:
            continue
        if route_num < 1 or route_num > 999:
            result.issues.append(
                Issue(
                    check_name="route_plausibility",
                    description=(f"Route number {route_num} seems implausible (expected 1-999)."),
                    severity="error",
                )
            )


def _check_delay_plausibility(response: str, result: ValidationResult) -> None:
    """Flag delay values that are negative or exceed 24 hours."""
    for idx, match in enumerate(_DELAY_PATTERN.finditer(response)):
        if idx >= _MAX_REGEX_ITERATIONS:
            break
        try:
            delay_val = float(match.group(1))
        except ValueError:
            continue
        unit_text = match.group(0).lower()
        is_seconds = "second" in unit_text or "sekund" in unit_text
        delay_minutes = delay_val / 60.0 if is_seconds else delay_val

        if delay_val < 0:
            result.issues.append(
                Issue(
                    check_name="delay_plausibility",
                    description=(
                        f"Negative delay value ({match.group(0).strip()}) detected. "
                        "Delays should be non-negative."
                    ),
                    severity="error",
                )
            )
        elif delay_minutes > 1440:
            result.issues.append(
                Issue(
                    check_name="delay_plausibility",
                    description=(
                        f"Delay of {match.group(0).strip()} exceeds 24 hours and may be incorrect."
                    ),
                    severity="error",
                )
            )


def _check_stale_data(result: ValidationResult, ctx: ValidationContext) -> None:
    """Warn if the response is based on stale cached data.

    Inspects two sources:
    1. The module-level circuit-breaker flag (``last_stale_data_timestamp``).
    2. Per-response: ``timestamp`` fields in transit tool JSON returns.

    Both branches emit ``warning``-severity issues — retrying will not
    refresh the upstream feed.
    """
    global last_stale_data_timestamp

    if last_stale_data_timestamp > 0:
        age = time.monotonic() - last_stale_data_timestamp
        if age < _STALE_DATA_THRESHOLD:
            result.issues.append(
                Issue(
                    check_name="stale_data",
                    description=(
                        "This response may be based on cached data. "
                        "Live feed was temporarily unavailable."
                    ),
                    severity="warning",
                )
            )

    now_ts = time.time()
    for record in ctx.tool_returns:
        if not any(record.tool_name.startswith(t) for t in _TRANSIT_TOOLS_WITH_TIMESTAMPS):
            continue
        try:
            raw_payload: object = record.payload
            if not isinstance(raw_payload, dict):
                continue
            payload_dict = cast(dict[str, object], raw_payload)
            ts = payload_dict.get("timestamp")
            if not isinstance(ts, (int, float, str)):
                continue
            age = now_ts - float(ts)
        except (TypeError, ValueError):
            continue
        if age > _STALE_DATA_THRESHOLD:
            result.issues.append(
                Issue(
                    check_name="stale_data",
                    description=(
                        f"GTFS-RT data from {record.tool_name} is "
                        f"{int(age)}s old (threshold {int(_STALE_DATA_THRESHOLD)}s)."
                    ),
                    severity="warning",
                )
            )
            return  # one warning is enough — avoid spam


def _check_latvian_diacritics(response: str, result: ValidationResult) -> None:
    """Warn if Latvian place names appear without expected diacritics."""
    for ascii_form, correct_form in _LATVIAN_DIACRITICS.items():
        if ascii_form == correct_form:
            continue
        if ascii_form in response and correct_form not in response:
            result.issues.append(
                Issue(
                    check_name="latvian_diacritics",
                    description=(
                        f"Latvian diacritics may be missing: "
                        f"'{ascii_form}' should likely be '{correct_form}'."
                    ),
                    severity="error",
                )
            )


def _check_route_existence(
    response: str,
    result: ValidationResult,
    ctx: ValidationContext,
) -> None:
    """Verify mentioned route numbers exist in GTFS static data.

    No-op if ``ctx.static_cache`` is unavailable or empty. Errors are
    retryable: the agent should re-answer using a route number that
    actually exists in the GTFS feed.
    """
    cache: GTFSStaticCache | None = ctx.static_cache
    if cache is None:
        return
    try:
        known_short_names: set[str] = {info.route_short_name for info in cache.routes.values()}
    except AttributeError:
        return
    if not known_short_names:
        return  # cache loaded but empty — fail-open
    seen: set[str] = set()
    for idx, match in enumerate(_ROUTE_PATTERN.finditer(response)):
        if idx >= _MAX_REGEX_ITERATIONS:
            break
        route_token = match.group(1)
        if route_token in seen:
            continue
        seen.add(route_token)
        if route_token not in known_short_names:
            result.issues.append(
                Issue(
                    check_name="route_existence",
                    description=(
                        f"Route {route_token} not found in GTFS data. Use a real route number."
                    ),
                    severity="error",
                )
            )


def _normalize_lv(text: str) -> str:
    """Lowercase + strip Latvian diacritics for fuzzy matching."""
    table = str.maketrans(
        "\u0101\u010d\u0113\u0123\u012b\u0137\u013c\u0146\u0161\u016b\u017e"
        "\u0100\u010c\u0112\u0122\u012a\u0136\u013b\u0145\u0160\u016a\u017d",
        "acegiklnsuzACEGIKLNSUZ",
    )
    return text.translate(table).lower().strip()


def _check_stop_existence(
    response: str,
    result: ValidationResult,
    ctx: ValidationContext,
) -> None:
    """Warn if a mentioned stop name doesn't appear in GTFS static data.

    Severity is ``warning`` (not ``error``) because stop-name extraction
    is heuristic and false positives are likely. The check no-ops when
    the cache is unavailable or empty.
    """
    cache: GTFSStaticCache | None = ctx.static_cache
    if cache is None:
        return
    try:
        if not cache.stops:
            return
        known_names = {_normalize_lv(s.stop_name) for s in cache.stops.values()}
    except AttributeError:
        return
    seen_norms: set[str] = set()
    for idx, match in enumerate(_STOP_PATTERN.finditer(response)):
        if idx >= _MAX_REGEX_ITERATIONS:
            break
        candidate = match.group(1).strip()
        norm = _normalize_lv(candidate)
        if norm in seen_norms:
            continue
        seen_norms.add(norm)
        # Substring match either way — agent might say "Brīvības" but the
        # full stop is "Brīvības iela 12". Treat partial as found.
        if not any(norm in k or k in norm for k in known_names):
            result.issues.append(
                Issue(
                    check_name="stop_existence",
                    description=(f"Stop '{candidate}' not found in GTFS data — verify name."),
                    severity="warning",
                )
            )


def _check_time_consistency(response: str, result: ValidationResult) -> None:
    """Flag impossible HH:MM[:SS] times in the response.

    GTFS itself supports hours 24-47 for next-day trips, but agent text
    addressed to dispatchers should always normalise to 00-23. Errors
    are retryable.
    """
    for idx, match in enumerate(_TIME_PATTERN.finditer(response)):
        if idx >= _MAX_REGEX_ITERATIONS:
            break
        try:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3)) if match.group(3) else 0
        except ValueError:
            continue
        problems: list[str] = []
        if hours > 23:
            problems.append(f"hours={hours}")
        if minutes >= 60:
            problems.append(f"minutes={minutes}")
        if seconds >= 60:
            problems.append(f"seconds={seconds}")
        if problems:
            result.issues.append(
                Issue(
                    check_name="time_consistency",
                    description=(f"Impossible time '{match.group(0)}' ({', '.join(problems)})."),
                    severity="error",
                )
            )


def _harvest_document_ids(payload: Any) -> set[int] | None:  # noqa: ANN401
    """Extract `document_id` ints from a search_knowledge tool return.

    Args:
        payload: Parsed JSON payload (list of dicts, dict with ``results``,
            or anything else).

    Returns:
        Set of document ids found, or ``None`` if the payload was
        malformed (caller should fail-open in that case).
    """
    try:
        entries_obj: object
        if isinstance(payload, list):
            entries_obj = cast(list[object], payload)
        elif isinstance(payload, dict):
            payload_dict = cast(dict[str, object], payload)
            entries_obj = payload_dict.get("results", [])
        else:
            return set()
        if not isinstance(entries_obj, list):
            return set()
        ids: set[int] = set()
        for entry in cast(list[object], entries_obj):
            if not isinstance(entry, dict):
                continue
            entry_dict = cast(dict[str, object], entry)
            raw_id = entry_dict.get("document_id")
            if isinstance(raw_id, int):
                ids.add(raw_id)
            elif isinstance(raw_id, str) and raw_id.isdigit():
                ids.add(int(raw_id))
        return ids
    except (AttributeError, TypeError, ValueError):
        return None


def _check_citation_grounding(
    response: str,
    result: ValidationResult,
    ctx: ValidationContext,
) -> None:
    """Verify Markdown citations point to documents the agent retrieved.

    Iterates ``ctx.tool_returns`` for any tool whose name starts with
    ``search_knowledge``, harvests the union of returned ``document_id``
    values, then flags every cited ID that's not in that set. Fails
    open on malformed payloads — we can't prove fabrication if we can't
    parse the tool data.
    """
    if not ctx.tool_returns:
        return
    valid_ids: set[int] = set()
    saw_search = False
    for record in ctx.tool_returns:
        if not record.tool_name.startswith("search_knowledge"):
            continue
        saw_search = True
        ids = _harvest_document_ids(record.payload)
        if ids is None:
            return  # malformed payload — fail-open
        valid_ids.update(ids)
    if not saw_search:
        return  # no knowledge tool calls → no citations expected
    seen: set[int] = set()
    for idx, match in enumerate(_CITATION_PATTERN.finditer(response)):
        if idx >= _MAX_REGEX_ITERATIONS:
            break
        try:
            doc_id = int(match.group(1))
        except ValueError:
            continue
        if doc_id in seen:
            continue
        seen.add(doc_id)
        if doc_id not in valid_ids:
            result.issues.append(
                Issue(
                    check_name="citation_grounding",
                    description=(
                        f"Citation references document {doc_id} which "
                        "was not returned by search_knowledge."
                    ),
                    severity="error",
                )
            )


def _detect_language(text: str) -> Literal["lv", "en"]:
    """Cheap regex-based language detector for lv vs en.

    Counts Latvian-only diacritics and English stopwords. Defaults to
    ``"lv"`` on ties — Latvian is the primary platform language.
    """
    diacritic_count = sum(1 for c in text if c in _LV_DIACRITIC_CHARS)
    if diacritic_count >= 2:
        return "lv"
    stopword_hits = len(_EN_STOPWORD_PATTERN.findall(text))
    if stopword_hits >= 2:
        return "en"
    return "lv"


def _check_language_match(
    response: str,
    result: ValidationResult,
    ctx: ValidationContext,
) -> None:
    """Flag responses written in a different language than the user prompt."""
    if not ctx.user_message:
        return
    user_lang = _detect_language(ctx.user_message)
    response_lang = _detect_language(response)
    if user_lang != response_lang:
        result.issues.append(
            Issue(
                check_name="language_match",
                description=(
                    f"Response language does not match the user's language "
                    f"({user_lang} → {response_lang})."
                ),
                severity="error",
            )
        )


__all__ = [
    "Issue",
    "Severity",
    "ToolReturnRecord",
    "ValidationContext",
    "ValidationResult",
    "extract_tool_returns",
    "last_stale_data_timestamp",
    "validate_transit_response",
]
