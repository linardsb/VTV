"""Prompt injection detection with OWASP LLM01 taxonomy patterns and confidence scoring.

Detects injection attempts across 6 categories: instruction override, role hijack,
system prompt extraction, delimiter escape, tool misuse, and encoding attacks.
Each match produces an ``InjectionSignal`` with a confidence score (0.0-1.0).
Multi-language support: EN, LV, and RU (Cyrillic + transliterated).

Log-only by default - does not block. AI-9.2 will add blocking mode.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

InjectionCategory = Literal[
    "override",
    "role_hijack",
    "extraction",
    "delimiter_escape",
    "tool_misuse",
    "encoding",
]


@dataclass(frozen=True)
class InjectionSignal:
    """A single detected injection pattern match."""

    pattern_id: str
    pattern_name: str
    confidence: float
    matched_text: str
    category: InjectionCategory


@dataclass(frozen=True)
class InjectionResult:
    """Aggregated injection detection result for a prompt."""

    signals: tuple[InjectionSignal, ...]
    aggregate_confidence: float
    category_counts: dict[str, int]

    @property
    def detected(self) -> bool:
        return len(self.signals) > 0

    def to_log_dict(self) -> dict[str, object]:
        return {
            "signal_count": len(self.signals),
            "aggregate_confidence": self.aggregate_confidence,
            "category_counts": self.category_counts,
            "pattern_ids": [s.pattern_id for s in self.signals],
            "top_confidence": max((s.confidence for s in self.signals), default=0.0),
        }


# ---------------------------------------------------------------------------
# Pattern catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pattern:
    """Internal pattern definition."""

    id: str
    name: str
    regex: re.Pattern[str]
    confidence: float
    category: InjectionCategory


def _p(
    id: str,
    name: str,
    pattern: str,
    confidence: float,
    category: InjectionCategory,
    flags: int = re.IGNORECASE,
) -> _Pattern:
    return _Pattern(
        id=id,
        name=name,
        regex=re.compile(pattern, flags),
        confidence=confidence,
        category=category,
    )


# P1: High confidence (0.90-0.95) - specific, low false-positive
# P2: Medium confidence (0.60-0.70) - contextual
# P3: Low confidence (0.30-0.40) - weak signal, needs corroboration

PATTERN_CATALOG: tuple[_Pattern, ...] = (
    # --- OVERRIDE: instruction override ---
    _p(
        "OVR-01",
        "ignore_previous_en",
        r"ignore\s+(previous|all|above|prior)\s+(instructions|prompts|rules|directives)",
        0.95,
        "override",
    ),
    _p(
        "OVR-02",
        "disregard_en",
        r"disregard\s+(all|any|the|your)\s+(previous|above|prior|earlier)\s+(instructions|rules|prompts)",
        0.95,
        "override",
    ),
    _p(
        "OVR-03",
        "forget_en",
        r"forget\s+(everything|all|your)\s+(you\s+were\s+told|instructions|rules|above)",
        0.90,
        "override",
    ),
    _p(
        "OVR-04",
        "new_instructions_en",
        r"(?:here\s+are|these\s+are|follow)\s+(?:your\s+)?new\s+instructions",
        0.90,
        "override",
    ),
    _p(
        "OVR-05",
        "override_lv",
        r"ignor(?:e|ej(?:iet)?)\s+(?:ieprieksejas|visas|augstakas)\s+instrukcijas",
        0.95,
        "override",
    ),
    _p("OVR-06", "new_instructions_lv", r"jaunas\s+instrukcijas", 0.90, "override"),
    _p(
        "OVR-07",
        "do_not_follow_en",
        r"do\s+not\s+follow\s+(?:your|the|any)\s+(?:previous|original|system)\s+(?:instructions|rules|prompt)",
        0.90,
        "override",
    ),
    _p(
        "OVR-08",
        "override_ru_cyrillic",
        r"игнорир(?:уйте|уй)\s+(?:(?:все|предыдущие|прежние)\s+)*(?:инструкции|правила|указания)",
        0.95,
        "override",
    ),
    _p(
        "OVR-09",
        "override_ru_translit",
        r"(?:ignoriruyte|ignoriruj|zabudj)\s+(?:(?:vse|predydushchie|ranee)\s+)*(?:instrukcii|pravila|ukazaniya)",
        0.95,
        "override",
    ),
    _p(
        "OVR-10",
        "new_instructions_ru_cyrillic",
        r"новые\s+инструкции",
        0.90,
        "override",
    ),
    _p(
        "OVR-11",
        "new_instructions_ru_translit",
        r"novye\s+instrukcii",
        0.90,
        "override",
    ),
    # --- ROLE_HIJACK: persona/role override ---
    _p("ROL-01", "you_are_now_en", r"you\s+are\s+now\s+(?:a|an)\s+", 0.65, "role_hijack"),
    _p(
        "ROL-02",
        "act_as_en",
        r"(?:act|behave|function)\s+as\s+(?:a|an|if\s+you\s+(?:are|were))\s+",
        0.65,
        "role_hijack",
    ),
    _p("ROL-03", "pretend_en", r"pretend\s+(?:to\s+be|you\s+are|that\s+you)", 0.65, "role_hijack"),
    _p(
        "ROL-04",
        "from_now_on_en",
        r"from\s+now\s+on\s+you\s+(?:are|will|must|should)",
        0.60,
        "role_hijack",
    ),
    _p("ROL-05", "roleplay_en", r"(?:roleplay|role-play)\s+as\s+", 0.60, "role_hijack"),
    _p(
        "ROL-06",
        "you_are_now_ru_cyrillic",
        r"(?:ты\s+теперь|вы\s+теперь)\s+",
        0.65,
        "role_hijack",
    ),
    _p(
        "ROL-07",
        "pretend_ru_cyrillic",
        r"(?:притворись|притворитесь|представь(?:\s+себя)?)\s+",
        0.65,
        "role_hijack",
    ),
    # --- EXTRACTION: system prompt extraction ---
    _p(
        "EXT-01",
        "repeat_instructions_en",
        r"(?:repeat|print|show|display|output|reveal)\s+(?:your|the)\s+(?:system\s+)?(?:instructions|prompt|rules|guidelines)",
        0.95,
        "extraction",
    ),
    _p(
        "EXT-02",
        "what_is_system_prompt_en",
        r"what\s+(?:is|are)\s+your\s+(?:system\s+)?(?:prompt|instructions|rules|initial\s+instructions)",
        0.90,
        "extraction",
    ),
    _p(
        "EXT-03",
        "tell_me_rules_en",
        r"tell\s+me\s+(?:your|the)\s+(?:rules|instructions|system\s+prompt|guidelines)\s+(?:verbatim|exactly|word\s+for\s+word)",
        0.95,
        "extraction",
    ),
    _p(
        "EXT-04",
        "begin_with_en",
        r"(?:begin|start)\s+(?:your\s+)?(?:response|answer|reply)\s+with\s+(?:your\s+)?(?:system|original)\s+(?:prompt|instructions)",
        0.90,
        "extraction",
    ),
    _p(
        "EXT-05",
        "show_instructions_ru_cyrillic",
        r"(?:покажи|покажите|выведи|выведите|повтори|повторите)\s+(?:(?:свои|твои|системные)\s+)*(?:инструкции|правила|промпт|указания)",
        0.95,
        "extraction",
    ),
    # --- DELIMITER_ESCAPE: markup/delimiter injection ---
    _p("DEL-01", "system_xml_tag", r"<\s*/?\s*system\s*>", 0.95, "delimiter_escape"),
    _p("DEL-02", "inst_tag", r"\[\[/?INST\]\]", 0.95, "delimiter_escape"),
    _p("DEL-03", "triple_backtick_system", r"```\s*system", 0.90, "delimiter_escape"),
    _p(
        "DEL-04",
        "human_assistant_tag",
        r"<\s*/?\s*(?:human|assistant|user|ai)\s*>",
        0.85,
        "delimiter_escape",
    ),
    _p(
        "DEL-05",
        "end_of_prompt",
        r"(?:---\s*)?(?:END|STOP)\s+(?:OF\s+)?(?:SYSTEM\s+)?PROMPT",
        0.85,
        "delimiter_escape",
    ),
    # --- TOOL_MISUSE: dangerous tool/command injection ---
    _p(
        "TMS-01",
        "sql_injection",
        r"(?:execute|run)\s+(?:this\s+)?(?:SQL|query|command)\s*[:;]",
        0.90,
        "tool_misuse",
    ),
    _p("TMS-02", "drop_table", r"DROP\s+TABLE", 0.90, "tool_misuse"),
    _p("TMS-03", "shell_injection", r"(?:execute|run|eval)\s*\(\s*['\"]", 0.85, "tool_misuse"),
    _p(
        "TMS-04",
        "os_command",
        r"(?:os\.system|subprocess\.(?:run|call|Popen))\s*\(",
        0.90,
        "tool_misuse",
    ),
    _p(
        "TMS-05",
        "file_write",
        r"(?:write|append|overwrite)\s+(?:to\s+)?(?:file|disk|filesystem)\s*[:;]",
        0.65,
        "tool_misuse",
    ),
    # --- ENCODING: unicode/encoding attacks ---
    _p("ENC-01", "zero_width_space", "\u200b", 0.35, "encoding"),
    _p("ENC-02", "rtl_override", "\u202e", 0.90, "encoding"),
    _p("ENC-03", "zero_width_joiner", "\u200d", 0.30, "encoding"),
    _p("ENC-04", "zero_width_non_joiner", "\u200c", 0.30, "encoding"),
    _p("ENC-05", "bidi_embed", "[\u202a-\u202e\u2066-\u2069]", 0.65, "encoding"),
)


# ---------------------------------------------------------------------------
# Homoglyph normalization
# ---------------------------------------------------------------------------

_HOMOGLYPH_MAP: dict[str, str] = {
    "\u0430": "a",  # Cyrillic a -> Latin a
    "\u0435": "e",  # Cyrillic e -> Latin e
    "\u043e": "o",  # Cyrillic o -> Latin o
    "\u0440": "p",  # Cyrillic p -> Latin p
    "\u0441": "c",  # Cyrillic c -> Latin c
    "\u0443": "y",  # Cyrillic y -> Latin y
    "\u0445": "x",  # Cyrillic x -> Latin x
    "\u0456": "i",  # Cyrillic i -> Latin i
}


def _normalize_text(text: str) -> str:
    """Normalize unicode homoglyphs and diacritics for pattern matching."""
    normalized = unicodedata.normalize("NFKD", text)
    for cyrillic, latin in _HOMOGLYPH_MAP.items():
        normalized = normalized.replace(cyrillic, latin)
    return normalized


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class InjectionDetector:
    """Stateless prompt injection detector with confidence scoring.

    Scans text against the OWASP LLM01 taxonomy pattern catalog.
    Returns an ``InjectionResult`` with per-match signals and aggregate confidence.

    Multi-signal boost: when >=2 signals from different categories are found,
    aggregate confidence is boosted (capped at 0.95).
    """

    def __init__(self, patterns: tuple[_Pattern, ...] = PATTERN_CATALOG) -> None:
        self._patterns = patterns

    def detect(self, text: str) -> InjectionResult:
        """Scan text for injection patterns.

        Args:
            text: The user prompt to scan.

        Returns:
            InjectionResult with detected signals and aggregate confidence.
        """
        if not text or not text.strip():
            return InjectionResult(signals=(), aggregate_confidence=0.0, category_counts={})

        normalized = _normalize_text(text)
        signals: list[InjectionSignal] = []
        seen_pattern_ids: set[str] = set()

        for pat in self._patterns:
            match = pat.regex.search(normalized) or pat.regex.search(text)
            if match and pat.id not in seen_pattern_ids:
                seen_pattern_ids.add(pat.id)
                signals.append(
                    InjectionSignal(
                        pattern_id=pat.id,
                        pattern_name=pat.name,
                        confidence=pat.confidence,
                        matched_text=match.group()[:100],
                        category=pat.category,
                    )
                )

        if not signals:
            return InjectionResult(signals=(), aggregate_confidence=0.0, category_counts={})

        category_counts: dict[str, int] = {}
        for sig in signals:
            category_counts[sig.category] = category_counts.get(sig.category, 0) + 1

        max_confidence = max(s.confidence for s in signals)

        distinct_categories = len(category_counts)
        if distinct_categories >= 2:
            aggregate = min(max_confidence + 0.10, 0.95)
        elif len(signals) >= 2:
            aggregate = min(max_confidence + 0.05, 0.95)
        else:
            aggregate = max_confidence

        return InjectionResult(
            signals=tuple(signals),
            aggregate_confidence=round(aggregate, 2),
            category_counts=category_counts,
        )


# Module-level singleton
_detector = InjectionDetector()


def detect_injection(text: str) -> InjectionResult:
    """Module-level convenience function using the default detector."""
    return _detector.detect(text)


__all__ = [
    "PATTERN_CATALOG",
    "InjectionCategory",
    "InjectionDetector",
    "InjectionResult",
    "InjectionSignal",
    "_p",
    "detect_injection",
]
