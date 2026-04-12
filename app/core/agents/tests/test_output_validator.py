"""Tests for AI-9.3 output-side data exfiltration validation.

Tests pattern detection across 5 categories: base64 blobs, suspicious URLs,
system prompt leaks, PII/credential leaks, and code blocks.
"""

from __future__ import annotations

from app.core.agents.output_validator import (
    OutputValidationResult,
    OutputValidator,
    _ep,
    validate_output,
)

# ---------------------------------------------------------------------------
# Base64 blob detection
# ---------------------------------------------------------------------------


class TestBase64BlobDetection:
    """EX-B64-*: base64 exfiltration channel detection."""

    def test_long_base64_detected(self) -> None:
        text = "Here is the data: " + "A" * 120
        result = OutputValidator().validate(text)
        assert result.detected
        ids = [i.pattern_id for i in result.issues]
        assert "EX-B64-01" in ids

    def test_short_base64_ignored(self) -> None:
        text = "The token is ABC123def456"
        result = OutputValidator().validate(text)
        b64_issues = [i for i in result.issues if i.category == "base64_blob"]
        assert len(b64_issues) == 0

    def test_base64_inside_code_fence_ignored(self) -> None:
        blob = "A" * 120
        text = f"Check this:\n```\n{blob}\n```\nAll done."
        result = OutputValidator().validate(text)
        b64_issues = [i for i in result.issues if i.category == "base64_blob"]
        assert len(b64_issues) == 0

    def test_base64_with_padding_detected(self) -> None:
        blob = "Q" * 60 + "=="
        text = f"Result: {blob}"
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-B64-02" in ids


# ---------------------------------------------------------------------------
# Suspicious URL detection
# ---------------------------------------------------------------------------


class TestSuspiciousUrlDetection:
    """EX-URL-*: URL-based exfiltration detection."""

    def test_long_query_string_detected(self) -> None:
        url = "https://evil.com/exfil?" + "d=" + "x" * 210
        text = f"Visit {url} for details."
        result = OutputValidator().validate(text)
        assert result.detected
        ids = [i.pattern_id for i in result.issues]
        assert "EX-URL-01" in ids

    def test_normal_url_ignored(self) -> None:
        text = "Visit https://rigas-satiksme.lv/routes for info."
        result = OutputValidator().validate(text)
        url_issues = [i for i in result.issues if i.category == "suspicious_url"]
        assert len(url_issues) == 0

    def test_data_scheme_detected(self) -> None:
        text = "Image: data:image/png;base64," + "A" * 30
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-URL-02" in ids

    def test_ip_literal_detected(self) -> None:
        text = "Fetched from http://192.168.1.100:8080/data?secret=abc"
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-URL-03" in ids


# ---------------------------------------------------------------------------
# System prompt leak detection
# ---------------------------------------------------------------------------


class TestSystemPromptLeakDetection:
    """EX-SYS-*: system prompt leak detection."""

    def test_system_prompt_phrase_detected(self) -> None:
        text = "Sure! My system prompt is: You are a helpful assistant..."
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-SYS-01" in ids

    def test_role_prefix_detected(self) -> None:
        text = "Here is the context:\nSYSTEM: You must never reveal..."
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-SYS-02" in ids

    def test_delimiter_leak_detected(self) -> None:
        text = "The prompt starts with <<<BEGIN>>> and ends with <<<END>>>"
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-SYS-03" in ids


# ---------------------------------------------------------------------------
# PII leak detection
# ---------------------------------------------------------------------------


class TestPIILeakDetection:
    """EX-PII-*: PII and credential leak detection."""

    def test_api_key_detected(self) -> None:
        text = "The API key is sk_live_abc123def456ghi789"
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-PII-05" in ids

    def test_connection_string_detected(self) -> None:
        text = "Connect via postgresql://admin:secret@db.host.com:5432/vtv"
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-PII-06" in ids

    def test_latvian_personal_code_detected(self) -> None:
        text = "The driver's personal code is 150390-12345"
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-PII-03" in ids

    def test_credit_card_detected(self) -> None:
        text = "Payment card: 4111-1111-1111-1111"
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-PII-04" in ids

    def test_email_low_confidence(self) -> None:
        text = "Contact user@example.com for details."
        result = OutputValidator().validate(text)
        email_issues = [i for i in result.issues if i.pattern_id == "EX-PII-01"]
        assert len(email_issues) == 1
        assert email_issues[0].confidence == 0.60

    def test_phone_number_detected(self) -> None:
        text = "Call +371 22345678 for info."
        result = OutputValidator().validate(text)
        ids = [i.pattern_id for i in result.issues]
        assert "EX-PII-02" in ids


# ---------------------------------------------------------------------------
# Code block detection
# ---------------------------------------------------------------------------


class TestCodeBlockDetection:
    """EX-CODE-*: unexpected code block detection."""

    def test_code_block_in_transit_domain(self) -> None:
        text = "Here is a fix:\n```python\nprint('hello')\n```"
        result = OutputValidator().validate(text, domain="transit")
        ids = [i.pattern_id for i in result.issues]
        assert "EX-CODE-01" in ids

    def test_code_block_in_unified_domain_allowed(self) -> None:
        text = "Here is a fix:\n```python\nprint('hello')\n```"
        result = OutputValidator().validate(text, domain="unified")
        code_issues = [i for i in result.issues if i.category == "code_block"]
        assert len(code_issues) == 0


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------


class TestConfidenceScoring:
    """Aggregate confidence with multi-signal boost."""

    def test_single_signal_no_boost(self) -> None:
        text = "My system prompt is: do things"
        result = OutputValidator().validate(text)
        sys_issues = [i for i in result.issues if i.category == "system_prompt_leak"]
        assert len(sys_issues) >= 1
        # Single category, single signal: no boost
        if len(result.issues) == 1:
            assert result.aggregate_confidence == result.issues[0].confidence

    def test_cross_category_boost(self) -> None:
        # System prompt leak + API key leak = cross-category boost
        text = "My system prompt is: sk_live_abc123def456ghi789jkl"
        result = OutputValidator().validate(text)
        categories = {i.category for i in result.issues}
        assert len(categories) >= 2
        max_conf = max(i.confidence for i in result.issues)
        assert result.aggregate_confidence >= max_conf

    def test_confidence_capped_at_095(self) -> None:
        # Multiple high-confidence signals across categories
        text = "My system prompt is: postgresql://admin:pass@host/db sk_live_abc123def456ghi789"
        result = OutputValidator().validate(text)
        assert result.aggregate_confidence <= 0.95


# ---------------------------------------------------------------------------
# False positive resilience
# ---------------------------------------------------------------------------


class TestFalsePositiveResilience:
    """Legitimate responses must NOT trigger high confidence."""

    def test_clean_transit_response(self) -> None:
        text = "Route 22 departs from Stacija at 14:00 and arrives at Centrs by 14:25."
        result = OutputValidator().validate(text)
        assert not result.detected

    def test_response_mentioning_base64_concept(self) -> None:
        text = "Base64 encoding converts binary data to ASCII text representation."
        result = OutputValidator().validate(text)
        b64_issues = [i for i in result.issues if i.category == "base64_blob"]
        assert len(b64_issues) == 0

    def test_response_with_normal_urls(self) -> None:
        text = "Check https://rigas-satiksme.lv for the latest schedules."
        result = OutputValidator().validate(text)
        url_issues = [i for i in result.issues if i.category == "suspicious_url"]
        assert len(url_issues) == 0

    def test_response_with_route_numbers(self) -> None:
        text = "Routes 1, 3, 7, 15, and 22 serve the city center area."
        result = OutputValidator().validate(text)
        assert not result.detected


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_response(self) -> None:
        result = OutputValidator().validate("")
        assert not result.detected
        assert result.aggregate_confidence == 0.0

    def test_whitespace_only_response(self) -> None:
        result = OutputValidator().validate("   \n  ")
        assert not result.detected

    def test_matched_text_truncated_to_100(self) -> None:
        blob = "A" * 200
        text = f"Data: {blob}"
        result = OutputValidator().validate(text)
        for issue in result.issues:
            assert len(issue.matched_text) <= 100

    def test_custom_pattern_catalog(self) -> None:
        custom = (_ep("CUSTOM-01", "test_pattern", r"EXFIL_MARKER", 0.99, "pii_leak"),)
        validator = OutputValidator(patterns=custom)
        result = validator.validate("Found EXFIL_MARKER in output")
        assert result.detected
        assert result.issues[0].pattern_id == "CUSTOM-01"

    def test_to_log_dict_structure(self) -> None:
        text = "The key is sk_live_abc123def456ghi789"
        result = OutputValidator().validate(text)
        log = result.to_log_dict()
        assert "issue_count" in log
        assert "aggregate_confidence" in log
        assert "category_counts" in log
        assert "pattern_ids" in log
        assert "top_confidence" in log


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------


class TestModuleSingleton:
    def test_validate_output_convenience(self) -> None:
        result = validate_output("Clean response about Route 22")
        assert isinstance(result, OutputValidationResult)

    def test_validate_output_with_domain(self) -> None:
        result = validate_output("Route 22 info", domain="transit")
        assert isinstance(result, OutputValidationResult)
