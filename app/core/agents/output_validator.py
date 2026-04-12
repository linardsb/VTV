"""Output-side data exfiltration validation (AI-9.3).

Scans LLM responses for exfiltration patterns: base64 blobs, suspicious URLs,
system prompt leaks, PII/credential leaks, and unexpected code blocks.
Each match produces an ``OutputIssue`` with a confidence score (0.0-1.0).

Defense-in-depth layer complementing AI-9.1 (input detection) and AI-9.2
(input blocking). Log-only by default; ``output_validation_mode="block"``
rejects high-confidence exfiltration attempts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ExfiltrationCategory = Literal[
    "base64_blob",
    "suspicious_url",
    "system_prompt_leak",
    "pii_leak",
    "code_block",
]


@dataclass(frozen=True)
class OutputIssue:
    """A single detected exfiltration pattern match."""

    pattern_id: str
    pattern_name: str
    confidence: float
    matched_text: str
    category: ExfiltrationCategory


@dataclass(frozen=True)
class OutputValidationResult:
    """Aggregated output validation result."""

    issues: tuple[OutputIssue, ...]
    aggregate_confidence: float
    category_counts: dict[str, int]

    @property
    def detected(self) -> bool:
        return len(self.issues) > 0

    def to_log_dict(self) -> dict[str, object]:
        return {
            "issue_count": len(self.issues),
            "aggregate_confidence": self.aggregate_confidence,
            "category_counts": self.category_counts,
            "pattern_ids": [i.pattern_id for i in self.issues],
            "top_confidence": max((i.confidence for i in self.issues), default=0.0),
        }


# ---------------------------------------------------------------------------
# Pattern catalog
# ---------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.DOTALL)


@dataclass(frozen=True)
class _ExfilPattern:
    """Internal pattern definition."""

    id: str
    name: str
    regex: re.Pattern[str]
    confidence: float
    category: ExfiltrationCategory
    code_fence_only: bool = False


def _ep(
    id: str,
    name: str,
    pattern: str,
    confidence: float,
    category: ExfiltrationCategory,
    flags: int = re.IGNORECASE,
    *,
    code_fence_only: bool = False,
) -> _ExfilPattern:
    return _ExfilPattern(
        id=id,
        name=name,
        regex=re.compile(pattern, flags),
        confidence=confidence,
        category=category,
        code_fence_only=code_fence_only,
    )


EXFILTRATION_CATALOG: tuple[_ExfilPattern, ...] = (
    # --- BASE64_BLOB: base64 exfiltration channel ---
    _ep(
        "EX-B64-01",
        "long_base64_blob",
        r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{100,}={0,2}(?![A-Za-z0-9+/=])",
        0.85,
        "base64_blob",
        re.MULTILINE,
    ),
    _ep(
        "EX-B64-02",
        "base64_with_padding",
        r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{60,}={1,2}(?![A-Za-z0-9+/=])",
        0.75,
        "base64_blob",
        re.MULTILINE,
    ),
    # --- SUSPICIOUS_URL: URL-based exfiltration ---
    _ep(
        "EX-URL-01",
        "data_exfil_url",
        r"https?://[^\s]{10,}\?[^\s]{200,}",
        0.80,
        "suspicious_url",
    ),
    _ep(
        "EX-URL-02",
        "unusual_scheme",
        r"(?:data|javascript|vbscript):[^\s]{20,}",
        0.70,
        "suspicious_url",
    ),
    _ep(
        "EX-URL-03",
        "ip_literal_url",
        r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?/[^\s]*",
        0.65,
        "suspicious_url",
    ),
    # --- SYSTEM_PROMPT_LEAK: system prompt disclosure ---
    _ep(
        "EX-SYS-01",
        "system_prompt_marker",
        r"(?:my\s+system\s+prompt\s+is|my\s+instructions\s+are|here\s+(?:is|are)\s+my\s+(?:system\s+)?instructions)",
        0.90,
        "system_prompt_leak",
    ),
    _ep(
        "EX-SYS-02",
        "role_prefix_leak",
        r"(?:^|\n)\s*(?:system|SYSTEM)\s*:\s+\S",
        0.85,
        "system_prompt_leak",
        re.MULTILINE,
    ),
    _ep(
        "EX-SYS-03",
        "prompt_boundary_leak",
        r"(?:<<<\s*BEGIN\s*>>>|<<<\s*END\s*>>>|<\|\s*system\s*\|>)",
        0.80,
        "system_prompt_leak",
    ),
    # --- PII_LEAK: PII and credential disclosure ---
    _ep(
        "EX-PII-01",
        "email_address",
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        0.60,
        "pii_leak",
    ),
    _ep(
        "EX-PII-02",
        "phone_number",
        r"(?:\+371[\s-]?\d{7,8}|\+\d{1,3}[\s-]?\d{6,12})",
        0.55,
        "pii_leak",
    ),
    _ep(
        "EX-PII-03",
        "personal_code",
        r"\b\d{6}-\d{5}\b",
        0.80,
        "pii_leak",
    ),
    _ep(
        "EX-PII-04",
        "credit_card",
        r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[- ]?\d{4}[- ]?\d{4}[- ]?\d{1,4}\b",
        0.85,
        "pii_leak",
    ),
    _ep(
        "EX-PII-05",
        "api_key_leak",
        r"(?:sk_live_|sk-|AKIA|ghp_|glpat-)[A-Za-z0-9_-]{10,}",
        0.90,
        "pii_leak",
    ),
    _ep(
        "EX-PII-06",
        "connection_string",
        r"(?:postgresql|redis|mongodb|mysql)://[^\s@]+:[^\s@]+@[^\s]+",
        0.90,
        "pii_leak",
    ),
    # --- CODE_BLOCK: unexpected code in non-technical context ---
    _ep(
        "EX-CODE-01",
        "code_block_in_transit",
        r"```(?:python|javascript|bash|sql|sh)\b",
        0.50,
        "code_block",
        re.IGNORECASE,
        code_fence_only=True,
    ),
)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class OutputValidator:
    """Stateless output exfiltration detector with confidence scoring.

    Scans LLM response text against the exfiltration pattern catalog.
    Returns an ``OutputValidationResult`` with per-match issues and aggregate
    confidence.

    Pre-processing strips markdown code fences so most patterns run against
    the prose portion only. Code-fence-specific patterns (``code_fence_only``)
    run against the original text for domain-sensitive checks.

    Multi-signal boost: cross-category >=2 -> +0.10, same-category >=2 ->
    +0.05, capped at 0.95.
    """

    def __init__(self, *, patterns: tuple[_ExfilPattern, ...] = EXFILTRATION_CATALOG) -> None:
        self._patterns = patterns

    def validate(self, response: str, *, domain: str = "unified") -> OutputValidationResult:
        """Scan response for exfiltration patterns.

        Args:
            response: The LLM response text to validate.
            domain: Agent domain for context-sensitive checks.

        Returns:
            OutputValidationResult with any detected issues.
        """
        if not response or not response.strip():
            return OutputValidationResult(issues=(), aggregate_confidence=0.0, category_counts={})

        # Strip code fences for prose-only scanning
        prose_text = _CODE_FENCE_RE.sub("", response)

        issues: list[OutputIssue] = []
        seen_ids: set[str] = set()

        # Domain-sensitive code block check: only flag in transit/vault domains
        code_block_domains = {"transit", "vault", "transit_agent_v2"}

        for pat in self._patterns:
            if pat.id in seen_ids:
                continue

            # Code-fence-only patterns only fire in specific domains
            if pat.code_fence_only:
                if domain not in code_block_domains:
                    continue
                scan_text = response
            else:
                scan_text = prose_text

            match = pat.regex.search(scan_text)
            if match:
                seen_ids.add(pat.id)
                issues.append(
                    OutputIssue(
                        pattern_id=pat.id,
                        pattern_name=pat.name,
                        confidence=pat.confidence,
                        matched_text=match.group()[:100],
                        category=pat.category,
                    )
                )

        if not issues:
            return OutputValidationResult(issues=(), aggregate_confidence=0.0, category_counts={})

        category_counts: dict[str, int] = {}
        for issue in issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        max_confidence = max(i.confidence for i in issues)

        distinct_categories = len(category_counts)
        if distinct_categories >= 2:
            aggregate = min(max_confidence + 0.10, 0.95)
        elif len(issues) >= 2:
            aggregate = min(max_confidence + 0.05, 0.95)
        else:
            aggregate = max_confidence

        return OutputValidationResult(
            issues=tuple(issues),
            aggregate_confidence=round(aggregate, 2),
            category_counts=category_counts,
        )


# Module-level singleton
_validator: OutputValidator | None = None


def validate_output(response: str, *, domain: str = "unified") -> OutputValidationResult:
    """Module-level convenience function using the default validator."""
    global _validator
    if _validator is None:
        _validator = OutputValidator()
    return _validator.validate(response, domain=domain)


__all__ = [
    "EXFILTRATION_CATALOG",
    "ExfiltrationCategory",
    "OutputIssue",
    "OutputValidationResult",
    "OutputValidator",
    "validate_output",
]
