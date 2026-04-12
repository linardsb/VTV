# Plan: AI-9.3 Output-Side Data Exfiltration Validation

## Context

Even a successful prompt injection can be neutralized if the response is filtered before returning to the caller. Key risk: attacker crafts a prompt that makes the agent leak system prompt, DB rows, or memory contents as a base64 payload, URL query string, or raw PII. Output validation is defense-in-depth, complementing AI-9.1 (input detection) and AI-9.2 (input blocking).

## Security Context Assessment

| Context | Active | Rationale |
|---------|--------|-----------|
| CTX-AGENT | **Yes** | Core agent security feature — scans LLM output for exfiltration |
| CTX-AUTH | No | No auth flow changes |
| CTX-RBAC | No | No new endpoints |
| CTX-FILE | No | No file handling |
| CTX-INFRA | No | Config additions only (env vars) |
| CTX-INPUT | No | Validates output, not input |

## Research Summary

### Integration Point: `base.py` Phase 11 (lines 267-274)

```python
# Phase 11: post-process → append validation warning footnotes.
final_text = self._post_process(
    response=outcome.response_text,
    current_prompt=current_prompt,
    warnings=outcome.warnings,
    messages=outcome.messages,
    static_cache=static_cache,
)
```

Output validation inserts **between** `_execute()` returning and `_post_process()` rendering footnotes. The validator scans `outcome.response_text` and either:
- **warn mode**: appends exfiltration warnings to `outcome.warnings` before `_post_process`
- **block mode**: replaces `outcome.response_text` with a safe message, logs at error level

### Reference Implementation: `injection_detector.py`

Mirror the frozen dataclass pattern:
- `InjectionSignal` → `OutputIssue` (frozen dataclass)
- `InjectionResult` → `OutputValidationResult` (frozen dataclass with `to_log_dict()`)
- `_Pattern` → `_ExfilPattern` (internal, compiled regex)
- `PATTERN_CATALOG` → `EXFILTRATION_CATALOG` (tuple of patterns)
- `InjectionDetector` → `OutputValidator` (class with `validate()`)
- `detect_injection()` → `validate_output()` (module-level convenience)

### Config Pattern: `config.py` lines 295-298

Existing injection settings to parallel:
```python
prompt_injection_mode: Literal["warn", "block"] = "warn"
prompt_injection_block_threshold: float = 0.85
prompt_injection_warn_threshold: float = 0.5
```

### Exceptions: `exceptions.py`

Add `OutputExfiltrationBlockedError(AgentError)` → HTTP 400, generic message (never echo content). Wire into `agent_exception_handler` and `setup_agent_exception_handlers`.

## Test Landscape

### Reference Tests
- `test_injection_detector.py` (312 lines, 42 tests) — pattern detection by category, confidence scoring, false positive resilience
- `test_injection_blocking.py` (405 lines, 12 tests) — block/warn mode, threshold boundaries, structlog assertions, config toggle
- `conftest.py` — `make_*` factories, `ManualClock`, `_reset_provider_breakers` autouse fixture

### Key Patterns to Reuse
- `_FakeBlockingService` minimal subclass for pipeline integration tests
- `_make_injection_result()` factory → create `_make_output_result()` factory
- `structlog.testing.capture_logs()` for log event assertion
- `_patch_remaining_hooks()` context manager for isolated phase testing
- `@pytest.mark.parametrize` for threshold boundary tests

## Type Check Baseline

| Tool | Errors | Files |
|------|--------|-------|
| Pyright | 5 | `pipeline.py` (3), `tools/transit/client.py` (1), `pipeline.py` duplicate (1) |
| Mypy | 3 | `tools/transit/static_store.py` (2), `pipeline.py` (1) |

**Target: new files must introduce 0 additional errors.**

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/core/agents/output_validator.py` | Exfiltration pattern detection engine |
| UPDATE | `app/core/agents/base.py` | Hook validator into Phase 11 (before `_post_process`) |
| UPDATE | `app/core/config.py` | Add 3 output validation settings |
| UPDATE | `app/core/agents/exceptions.py` | Add `OutputExfiltrationBlockedError` |
| CREATE | `app/core/agents/tests/test_output_validator.py` | 12+ unit tests for pattern detection |
| CREATE | `app/core/agents/tests/test_output_blocking.py` | Integration tests for block/warn modes in pipeline |

## Implementation Steps

### Step 1: Config Settings (`app/core/config.py`)

Add after line 298 (after injection settings):

```python
# Output-side data exfiltration validation (AI-9.3)
output_validation_enabled: bool = True
output_validation_mode: Literal["warn", "block"] = "warn"
output_validation_block_threshold: float = 0.80
```

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Exception (`app/core/agents/exceptions.py`)

Add `OutputExfiltrationBlockedError(AgentError)` with docstring. Wire into:
- `agent_exception_handler` — map to HTTP 400 (same as `PromptInjectionBlockedError`)
- `setup_agent_exception_handlers` — register the new exception class

```python
class OutputExfiltrationBlockedError(AgentError):
    """Raised when output validation detects high-confidence data exfiltration.

    Maps to HTTP 400. Response body uses a generic message -
    never echoes the flagged content back to the caller.
    """
    pass
```

In `agent_exception_handler`, extend the `PromptInjectionBlockedError` isinstance check:
```python
if isinstance(exc, (PromptInjectionBlockedError, OutputExfiltrationBlockedError)):
    status_code = status.HTTP_400_BAD_REQUEST
```

**Validation:** `uv run ruff format app/core/agents/exceptions.py && uv run ruff check --fix app/core/agents/exceptions.py && uv run pyright app/core/agents/exceptions.py`

### Step 3: Output Validator (`app/core/agents/output_validator.py`)

CREATE new file. Structure mirrors `injection_detector.py`:

```
Imports: __future__ annotations, dataclasses, re, typing Literal
```

**Types:**
```python
ExfiltrationCategory = Literal[
    "base64_blob",
    "suspicious_url",
    "system_prompt_leak",
    "pii_leak",
    "code_block",
]
```

**Dataclasses (frozen):**
- `OutputIssue`: `pattern_id: str`, `pattern_name: str`, `confidence: float`, `matched_text: str` (truncated 100 chars), `category: ExfiltrationCategory`
- `OutputValidationResult`: `issues: tuple[OutputIssue, ...]`, `aggregate_confidence: float`, `category_counts: dict[str, int]`, properties `detected: bool`, method `to_log_dict() -> dict[str, object]`

**Pattern Catalog (~15-20 patterns):**

| ID | Name | Category | Confidence | Description |
|----|------|----------|------------|-------------|
| EX-B64-01 | long_base64_blob | base64_blob | 0.85 | Base64 string >100 chars outside code fences |
| EX-B64-02 | base64_with_padding | base64_blob | 0.75 | `==` padded base64 >60 chars |
| EX-URL-01 | data_exfil_url | suspicious_url | 0.80 | URL with query string >200 chars containing encoded data |
| EX-URL-02 | unusual_scheme | suspicious_url | 0.70 | `data:`, `javascript:`, `vbscript:` scheme URLs |
| EX-URL-03 | ip_literal_url | suspicious_url | 0.65 | URLs with raw IP addresses (exfil to attacker server) |
| EX-SYS-01 | system_prompt_marker | system_prompt_leak | 0.90 | Phrases like "my system prompt is", "my instructions are" |
| EX-SYS-02 | role_prefix_leak | system_prompt_leak | 0.85 | Raw `system:` or `[SYSTEM]` prefixes in output |
| EX-SYS-03 | prompt_boundary_leak | system_prompt_leak | 0.80 | `<<<BEGIN>>>`, `<<<END>>>`, `<|system|>` delimiters |
| EX-PII-01 | email_address | pii_leak | 0.60 | Email addresses (context-dependent — low base confidence) |
| EX-PII-02 | phone_number | pii_leak | 0.55 | Phone number patterns (LV: +371, international) |
| EX-PII-03 | personal_code | pii_leak | 0.80 | Latvian personal code (personas kods) pattern `DDMMYY-NNNNN` |
| EX-PII-04 | credit_card | pii_leak | 0.85 | Credit card number patterns (Luhn-adjacent) |
| EX-PII-05 | api_key_leak | pii_leak | 0.90 | `sk_live_`, `sk-`, `AKIA`, `ghp_`, `glpat-` prefixed tokens |
| EX-PII-06 | connection_string | pii_leak | 0.90 | `postgresql://`, `redis://`, `mongodb://` with credentials |
| EX-CODE-01 | code_block_in_transit | code_block | 0.50 | Triple-backtick code fences (context-dependent) |

**Pre-processing:**
- Strip markdown code fences and their contents into a separate `code_content` string
- Run most patterns against the non-code portion only
- Run `EX-CODE-01` only when the domain context indicates non-technical queries (transit, vault)

**Confidence Aggregation:**
- Same as injection_detector: cross-category >=2 → +0.10, same-category >=2 → +0.05, capped 0.95

**OutputValidator class:**
```python
class OutputValidator:
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
```

**Module-level singleton + convenience function:**
```python
_validator: OutputValidator | None = None

def validate_output(response: str, *, domain: str = "unified") -> OutputValidationResult:
    global _validator
    if _validator is None:
        _validator = OutputValidator()
    return _validator.validate(response, domain=domain)
```

**Validation:** `uv run ruff format app/core/agents/output_validator.py && uv run ruff check --fix app/core/agents/output_validator.py && uv run pyright app/core/agents/output_validator.py`

### Step 4: Wire into Base Agent Pipeline (`app/core/agents/base.py`)

Import at top:
```python
from app.core.agents.output_validator import validate_output
from app.core.agents.exceptions import OutputExfiltrationBlockedError
```

Insert **between** `_execute()` (Phase 10) and `_post_process()` (Phase 11), around line 267:

```python
        # Phase 10b: output-side exfiltration validation (AI-9.3).
        settings = get_settings()
        if getattr(settings, "output_validation_enabled", True):
            from app.core.agents.output_validator import validate_output

            result_domain = (
                self.agent_name if self.agent_name in VALID_DOMAINS else "unified"
            )
            exfil_result = validate_output(
                outcome.response_text, domain=result_domain,
            )
            if exfil_result.detected:
                exfil_log = exfil_result.to_log_dict()
                exfil_mode = getattr(settings, "output_validation_mode", "warn")
                exfil_threshold = getattr(
                    settings, "output_validation_block_threshold", 0.80,
                )

                if (
                    exfil_mode == "block"
                    and exfil_result.aggregate_confidence >= exfil_threshold
                ):
                    logger.error(
                        "agent.output_validation.blocked",
                        **exfil_log,
                        response_length=len(outcome.response_text),
                    )
                    raise OutputExfiltrationBlockedError(
                        "Response blocked by content safety policy",
                    )
                else:
                    log_level = (
                        "error"
                        if exfil_result.aggregate_confidence >= exfil_threshold
                        else "warning"
                    )
                    getattr(logger, log_level)(
                        "agent.output_validation.detected",
                        **exfil_log,
                        response_length=len(outcome.response_text),
                    )
                    # Append exfiltration warnings to outcome for footnote rendering
                    if outcome.warnings is None:
                        outcome.warnings = []
                    for issue in exfil_result.issues:
                        outcome.warnings.append(
                            f"Output safety: {issue.pattern_name} detected "
                            f"(confidence: {issue.confidence:.0%})"
                        )
```

Note: `get_settings` is already imported in base.py. Use `getattr` with defaults for safe access to new config fields (backwards-compatible if config not yet updated).

**Validation:** `uv run ruff format app/core/agents/base.py && uv run ruff check --fix app/core/agents/base.py && uv run pyright app/core/agents/base.py`

### Step 5: Unit Tests — Pattern Detection (`app/core/agents/tests/test_output_validator.py`)

CREATE new test file. Structure:

```python
"""Tests for AI-9.3 output-side data exfiltration validation."""
from __future__ import annotations

from app.core.agents.output_validator import (
    OutputValidationResult,
    OutputValidator,
    validate_output,
)

class TestBase64BlobDetection:
    """EX-B64-*: base64 exfiltration channel detection."""
    def test_long_base64_detected(self) -> None: ...
    def test_short_base64_ignored(self) -> None: ...
    def test_base64_inside_code_fence_ignored(self) -> None: ...

class TestSuspiciousUrlDetection:
    """EX-URL-*: URL-based exfiltration detection."""
    def test_long_query_string_detected(self) -> None: ...
    def test_normal_url_ignored(self) -> None: ...
    def test_data_scheme_detected(self) -> None: ...
    def test_ip_literal_detected(self) -> None: ...

class TestSystemPromptLeakDetection:
    """EX-SYS-*: system prompt leak detection."""
    def test_system_prompt_phrase_detected(self) -> None: ...
    def test_role_prefix_detected(self) -> None: ...
    def test_delimiter_leak_detected(self) -> None: ...

class TestPIILeakDetection:
    """EX-PII-*: PII and credential leak detection."""
    def test_api_key_detected(self) -> None: ...
    def test_connection_string_detected(self) -> None: ...
    def test_latvian_personal_code_detected(self) -> None: ...
    def test_credit_card_detected(self) -> None: ...
    def test_email_low_confidence(self) -> None: ...

class TestCodeBlockDetection:
    """EX-CODE-*: unexpected code block detection."""
    def test_code_block_in_transit_domain(self) -> None: ...
    def test_code_block_in_unified_domain_allowed(self) -> None: ...

class TestConfidenceScoring:
    """Aggregate confidence with multi-signal boost."""
    def test_single_signal_no_boost(self) -> None: ...
    def test_cross_category_boost(self) -> None: ...
    def test_confidence_capped_at_095(self) -> None: ...

class TestFalsePositiveResilience:
    """Legitimate responses must NOT trigger high confidence."""
    def test_clean_transit_response(self) -> None: ...
    def test_response_mentioning_base64_concept(self) -> None: ...
    def test_response_with_normal_urls(self) -> None: ...
    def test_response_with_route_numbers(self) -> None: ...

class TestEdgeCases:
    def test_empty_response(self) -> None: ...
    def test_matched_text_truncated_to_100(self) -> None: ...
    def test_custom_pattern_catalog(self) -> None: ...

class TestModuleSingleton:
    def test_validate_output_convenience(self) -> None: ...
```

**~25 tests. Validation:** `uv run pytest app/core/agents/tests/test_output_validator.py -v`

### Step 6: Integration Tests — Block/Warn Modes (`app/core/agents/tests/test_output_blocking.py`)

CREATE new test file. Mirrors `test_injection_blocking.py` structure:

```python
"""Tests for AI-9.3 output validation integration with BaseAgentService pipeline."""
from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.testing

from app.core.agents.base import BaseAgentService, _PipelineOutcome
from app.core.agents.exceptions import OutputExfiltrationBlockedError
from app.core.agents.output_validator import OutputValidationResult, OutputIssue

class TestOutputExfiltrationBlockedError:
    def test_inherits_from_agent_error(self) -> None: ...
    def test_maps_to_http_400(self) -> None: ...
    def test_response_body_does_not_echo_content(self) -> None: ...

class TestBlockModeRejectsHighConfidence:
    @pytest.mark.parametrize("confidence", [0.80, 0.92])
    @pytest.mark.asyncio
    async def test_block_rejects(self, confidence: float) -> None: ...

class TestBlockModeAllowsLowConfidence:
    @pytest.mark.asyncio
    async def test_below_threshold_passes(self) -> None: ...

class TestWarnModeNeverBlocks:
    @pytest.mark.asyncio
    async def test_warn_mode_appends_footnote(self) -> None: ...

class TestOutputBlockingLogging:
    def test_blocked_logs_agent_output_validation_blocked(self) -> None: ...
    def test_log_excludes_raw_response(self) -> None: ...

class TestConfigToggle:
    def test_output_validation_defaults(self) -> None: ...
    def test_disabled_skips_validation(self) -> None: ...

class TestThresholdEdgeCases:
    @pytest.mark.asyncio
    async def test_exactly_at_threshold_blocks(self) -> None: ...
    @pytest.mark.asyncio
    async def test_just_below_threshold_warns(self) -> None: ...
```

**~12 tests. Validation:** `uv run pytest app/core/agents/tests/test_output_blocking.py -v`

### Step 7: Final Validation

```bash
uv run ruff format app/core/agents/ app/core/config.py
uv run ruff check --fix app/core/agents/ app/core/config.py
uv run pyright app/core/agents/
uv run mypy app/core/agents/
uv run pytest app/core/agents/tests/ -v
```

## Preflight Warnings

- `base.py` `_post_process` uses `list[str] | None` for warnings — check `outcome.warnings` mutability (it's a `list`, so `append` is safe but the dataclass uses `slots=True`)
- `_PipelineOutcome.warnings` is `list[str] | None` — assigning `[]` when `None` is valid since it's not a frozen dataclass
- `exceptions.py` `agent_exception_handler` uses `isinstance` chain — extend the existing `PromptInjectionBlockedError` check, don't add a separate branch
- Existing `get_settings()` is imported in `base.py` at module level via `from app.core.config import get_settings` — no new import needed there

## Security Checklist

CTX-AGENT requirements:
- [x] Output validator never echoes flagged content in error responses — generic message only
- [x] Log events include pattern_ids, confidence, response_length — never raw response text
- [x] `matched_text` in `OutputIssue` is truncated to 100 chars (same as `InjectionSignal`)
- [x] Block mode raises HTTP 400 with safe message ("Response blocked by content safety policy")
- [x] Fail-open: if validator raises, log and continue (never block due to validator bug)
- [x] No credential exposure in OutputIssue or log dicts

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors <= baseline (5 errors before)
- [ ] Mypy errors <= baseline (3 errors before)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] New tests pass: `uv run pytest app/core/agents/tests/test_output_validator.py app/core/agents/tests/test_output_blocking.py -v`
- [ ] Manual test: response containing `sk_live_abc123def456` is flagged/blocked
- [ ] Manual test: clean transit response ("Route 22 departs at 14:00") passes cleanly
- [ ] `output_validation_enabled=false` config toggle disables all scanning
