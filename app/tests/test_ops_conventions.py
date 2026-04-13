# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""OPS convention tests.

Validates that operational artifacts (SLO definitions, Prometheus alert rules,
runbooks, logging taxonomy) exist and have the correct structure.
"""

import subprocess
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALERTS_FILE = PROJECT_ROOT / "ops" / "prometheus" / "alerts.yml"
SLOS_FILE = PROJECT_ROOT / "docs" / "slos.md"
RUNBOOKS_DIR = PROJECT_ROOT / "docs" / "runbooks"
LOGGING_STANDARD_FILE = PROJECT_ROOT / "docs" / "logging-standard.md"
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_log_taxonomy.py"


class TestPrometheusAlertRules:
    """Validate Prometheus alert rules YAML structure (OPS-2.3)."""

    def test_alerts_file_exists(self) -> None:
        assert ALERTS_FILE.exists(), f"Alert rules file not found: {ALERTS_FILE}"

    def test_alerts_file_is_valid_yaml(self) -> None:
        content = ALERTS_FILE.read_text()
        rules = yaml.safe_load(content)
        assert isinstance(rules, dict), "Alert rules must be a YAML mapping"

    def test_alerts_have_groups_key(self) -> None:
        rules = yaml.safe_load(ALERTS_FILE.read_text())
        assert "groups" in rules, "Alert rules must have a top-level 'groups' key"
        assert isinstance(rules["groups"], list), "'groups' must be a list"
        assert len(rules["groups"]) > 0, "Must have at least one alert group"

    def test_each_group_has_name_and_rules(self) -> None:
        rules = yaml.safe_load(ALERTS_FILE.read_text())
        for group in rules["groups"]:
            assert "name" in group, f"Group missing 'name': {group}"
            assert "rules" in group, f"Group '{group['name']}' missing 'rules'"
            assert isinstance(group["rules"], list), f"Group '{group['name']}' rules must be a list"

    def test_each_rule_has_required_fields(self) -> None:
        rules = yaml.safe_load(ALERTS_FILE.read_text())
        required_fields = {"alert", "expr", "for", "labels", "annotations"}
        for group in rules["groups"]:
            for rule in group["rules"]:
                missing = required_fields - set(rule.keys())
                assert not missing, (
                    f"Rule '{rule.get('alert', '?')}' in group "
                    f"'{group['name']}' missing fields: {missing}"
                )

    def test_each_rule_has_severity_label(self) -> None:
        rules = yaml.safe_load(ALERTS_FILE.read_text())
        valid_severities = {"critical", "warning"}
        for group in rules["groups"]:
            for rule in group["rules"]:
                alert_name = rule.get("alert", "?")
                labels = rule.get("labels", {})
                assert "severity" in labels, f"Rule '{alert_name}' missing 'severity' label"
                assert labels["severity"] in valid_severities, (
                    f"Rule '{alert_name}' has invalid severity "
                    f"'{labels['severity']}', must be one of {valid_severities}"
                )

    def test_each_rule_has_required_annotations(self) -> None:
        rules = yaml.safe_load(ALERTS_FILE.read_text())
        required_annotations = {"summary", "description", "runbook_url"}
        for group in rules["groups"]:
            for rule in group["rules"]:
                alert_name = rule.get("alert", "?")
                annotations = rule.get("annotations", {})
                missing = required_annotations - set(annotations.keys())
                assert not missing, f"Rule '{alert_name}' missing annotations: {missing}"

    def test_runbook_urls_point_to_existing_files(self) -> None:
        rules = yaml.safe_load(ALERTS_FILE.read_text())
        for group in rules["groups"]:
            for rule in group["rules"]:
                alert_name = rule.get("alert", "?")
                runbook_url = rule.get("annotations", {}).get("runbook_url", "")
                runbook_path = PROJECT_ROOT / runbook_url
                assert runbook_path.exists(), (
                    f"Rule '{alert_name}' references runbook "
                    f"'{runbook_url}' but file does not exist at {runbook_path}"
                )

    def test_alert_names_are_unique(self) -> None:
        rules = yaml.safe_load(ALERTS_FILE.read_text())
        names: list[str] = []
        for group in rules["groups"]:
            for rule in group["rules"]:
                names.append(rule["alert"])
        duplicates = [n for n in names if names.count(n) > 1]
        assert not duplicates, f"Duplicate alert names: {set(duplicates)}"


class TestSLODefinitions:
    """Validate SLO documentation exists (OPS-2.3)."""

    def test_slos_file_exists(self) -> None:
        assert SLOS_FILE.exists(), f"SLO definitions not found: {SLOS_FILE}"

    def test_slos_file_has_content(self) -> None:
        content = SLOS_FILE.read_text()
        assert len(content) > 100, "SLO file appears to be empty or too short"

    def test_slos_file_references_runbooks(self) -> None:
        content = SLOS_FILE.read_text()
        assert "runbooks/" in content, "SLO file should reference runbooks for remediation"


class TestRunbooks:
    """Validate runbook files exist and have consistent structure."""

    EXPECTED_RUNBOOKS: ClassVar[list[str]] = [
        "credential-rotation.md",
        "high-latency.md",
        "high-error-rate.md",
        "circuit-breaker-open.md",
        "poller-stale.md",
        "db-pool-exhaustion.md",
    ]

    @pytest.mark.parametrize("runbook", EXPECTED_RUNBOOKS)
    def test_runbook_exists(self, runbook: str) -> None:
        path = RUNBOOKS_DIR / runbook
        assert path.exists(), f"Runbook not found: {path}"

    ALERT_RUNBOOKS: ClassVar[list[str]] = [
        "high-latency.md",
        "high-error-rate.md",
        "circuit-breaker-open.md",
        "poller-stale.md",
        "db-pool-exhaustion.md",
    ]

    @pytest.mark.parametrize("runbook", ALERT_RUNBOOKS)
    def test_alert_runbook_has_required_sections(self, runbook: str) -> None:
        content = (RUNBOOKS_DIR / runbook).read_text()
        required_headings = ["## Alert", "## Impact", "## Investigation", "## Remediation"]
        for heading in required_headings:
            assert heading in content, f"Runbook '{runbook}' missing section: {heading}"

    def test_runbooks_readme_lists_all_runbooks(self) -> None:
        readme = (RUNBOOKS_DIR / "README.md").read_text()
        for runbook in self.EXPECTED_RUNBOOKS:
            assert runbook in readme, f"Runbook '{runbook}' not listed in README.md"


class TestLoggingTaxonomy:
    """Validate logging taxonomy completeness (OPS-5.4)."""

    def test_logging_standard_exists(self) -> None:
        assert LOGGING_STANDARD_FILE.exists()

    def test_audit_script_exists(self) -> None:
        assert AUDIT_SCRIPT.exists()

    def test_no_undocumented_log_events(self) -> None:
        """Run audit script and assert zero undocumented events."""
        result = subprocess.run(  # noqa: S603
            ["uv", "run", "python", str(AUDIT_SCRIPT)],  # noqa: S607
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Logging taxonomy audit found undocumented events:\n{result.stdout}\n{result.stderr}"
        )
