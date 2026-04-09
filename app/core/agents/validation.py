"""Response validation for transit agent outputs.

Checks agent responses for plausibility issues (impossible route numbers,
unrealistic delays, missing diacritics) and flags stale data usage.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level flag: set to a monotonic timestamp when the agent serves
# data from a stale cache (circuit breaker fallback). Reset to 0.0 when
# fresh data is successfully fetched.
last_stale_data_timestamp: float = 0.0

# Threshold in seconds for considering cached data "stale" in warnings.
_STALE_DATA_THRESHOLD: float = 300.0  # 5 minutes

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


@dataclass
class ValidationResult:
    """Result of validating a transit agent response.

    Attributes:
        is_valid: True if no critical issues were found.
        warnings: List of human-readable warning messages.
        sanitized_response: The response text, potentially with annotations.
    """

    is_valid: bool = True
    warnings: list[str] = field(default_factory=list)
    sanitized_response: str = ""


def validate_transit_response(response: str) -> ValidationResult:
    """Validate a transit agent response for plausibility issues.

    Checks:
        1. Route numbers are within plausible range (1-999).
        2. Delay values are not negative or absurdly large (>1440 min / 24h).
        3. Stale data warning if serving from old cache.
        4. Latvian diacritics presence when response contains Latvian words.

    Args:
        response: The agent's text response to validate.

    Returns:
        ValidationResult with any warnings found.
    """
    result = ValidationResult(sanitized_response=response)

    _check_route_plausibility(response, result)
    _check_delay_plausibility(response, result)
    _check_stale_data(result)
    _check_latvian_diacritics(response, result)

    if result.warnings:
        result.is_valid = False

    return result


def _check_route_plausibility(response: str, result: ValidationResult) -> None:
    """Flag route numbers outside the plausible range 1-999."""
    for match in _ROUTE_PATTERN.finditer(response):
        route_num = int(match.group(1))
        if route_num < 1 or route_num > 999:
            result.warnings.append(f"Route number {route_num} seems implausible (expected 1-999).")


def _check_delay_plausibility(response: str, result: ValidationResult) -> None:
    """Flag delay values that are negative or exceed 24 hours."""
    for match in _DELAY_PATTERN.finditer(response):
        delay_val = float(match.group(1))
        # Determine if the unit is seconds or minutes from the matched text
        unit_text = match.group(0).lower()
        is_seconds = "second" in unit_text or "sekund" in unit_text

        delay_minutes = delay_val / 60.0 if is_seconds else delay_val

        if delay_val < 0:
            result.warnings.append(
                f"Negative delay value ({match.group(0).strip()}) detected. "
                "Delays should be non-negative."
            )
        elif delay_minutes > 1440:
            result.warnings.append(
                f"Delay of {match.group(0).strip()} exceeds 24 hours and may be incorrect."
            )


def _check_stale_data(result: ValidationResult) -> None:
    """Warn if the response is based on stale cached data."""
    global last_stale_data_timestamp

    if last_stale_data_timestamp > 0:
        age = time.monotonic() - last_stale_data_timestamp
        if age < _STALE_DATA_THRESHOLD:
            result.warnings.append(
                "This response may be based on cached data. Live feed was temporarily unavailable."
            )


def _check_latvian_diacritics(response: str, result: ValidationResult) -> None:
    """Warn if Latvian place names appear without expected diacritics."""
    for ascii_form, correct_form in _LATVIAN_DIACRITICS.items():
        if ascii_form == correct_form:
            continue
        # Check if the ASCII (wrong) form appears but the correct form does not
        if ascii_form in response and correct_form not in response:
            result.warnings.append(
                f"Latvian diacritics may be missing: "
                f"'{ascii_form}' should likely be '{correct_form}'."
            )
