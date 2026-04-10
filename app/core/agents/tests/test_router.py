"""Tests for AI-6.3 AgentRouter heuristic classifier."""

from __future__ import annotations

import json

import pytest

from app.core.agents.router import (
    AgentRouter,
    RoutingDecision,
    get_agent_router,
)
from app.core.logging import get_logger, setup_logging


@pytest.fixture
def router() -> AgentRouter:
    return AgentRouter()


class TestAgentRouterTransit:
    """Transit-domain prompt classification."""

    def test_latvian_route_delay(self, router: AgentRouter) -> None:
        assert router.route("Kuri maršruti kavējas?") == "transit"

    def test_latvian_route_delay_no_diacritics(self, router: AgentRouter) -> None:
        assert router.route("Kuri marsruti kavejas?") == "transit"

    def test_latvian_stop_query(self, router: AgentRouter) -> None:
        assert router.route("Kur ir tuvākā pietura?") == "transit"

    def test_english_delay_query(self, router: AgentRouter) -> None:
        assert router.route("Which routes are delayed?") == "transit"

    def test_english_schedule_query(self, router: AgentRouter) -> None:
        assert router.route("What's the bus schedule?") == "transit"

    def test_driver_query(self, router: AgentRouter) -> None:
        assert router.route("Kurš vadītājs ir reisā?") == "transit"


class TestAgentRouterKnowledge:
    """Knowledge-base prompt classification."""

    def test_latvian_procedure_query(self, router: AgentRouter) -> None:
        assert router.route("Kāda ir avārijas procedūra?") == "knowledge"

    def test_latvian_document_query(self, router: AgentRouter) -> None:
        assert router.route("Atrodi dokumentus par drošību") == "knowledge"

    def test_english_sop_query(self, router: AgentRouter) -> None:
        assert router.route("Show me the SOP for fueling") == "knowledge"

    def test_english_compliance_query(self, router: AgentRouter) -> None:
        assert router.route("What does the compliance regulation say?") == "knowledge"


class TestAgentRouterVault:
    """Vault / Obsidian prompt classification."""

    def test_vault_keyword(self, router: AgentRouter) -> None:
        assert router.route("Show my vault contents") == "vault"

    def test_obsidian_keyword(self, router: AgentRouter) -> None:
        assert router.route("Search obsidian for project X") == "vault"

    def test_latvian_notes_query(self, router: AgentRouter) -> None:
        assert router.route("Parādi manas piezīmes par tikšanos") == "vault"

    def test_folder_query(self, router: AgentRouter) -> None:
        assert router.route("List folders in my markdown collection") == "vault"


class TestAgentRouterUnified:
    """Cross-domain or signal-less prompts fall back to unified."""

    def test_empty_prompt(self, router: AgentRouter) -> None:
        assert router.route("") == "unified"

    def test_whitespace_only(self, router: AgentRouter) -> None:
        assert router.route("   ") == "unified"

    def test_unknown_topic(self, router: AgentRouter) -> None:
        assert router.route("Hello, how are you today?") == "unified"

    def test_cross_domain_transit_and_knowledge(self, router: AgentRouter) -> None:
        """Tied transit + knowledge scores -> unified."""
        assert router.route("What routes serve the hospitals mentioned in the SOP?") == "unified"

    def test_cross_domain_vault_and_transit(self, router: AgentRouter) -> None:
        """Vault note + delayed route -> tied -> unified."""
        assert router.route("Show vault notes about delayed buses") == "unified"


class TestRoutingDecisionScores:
    """Direct ``classify`` call surface."""

    def test_classify_returns_scores(self, router: AgentRouter) -> None:
        decision = router.classify("delayed buses")
        assert decision.transit_score >= 1
        assert decision.knowledge_score == 0
        assert decision.vault_score == 0

    def test_classify_returns_decision_namedtuple(self, router: AgentRouter) -> None:
        decision = router.classify("Which routes are delayed?")
        assert isinstance(decision, RoutingDecision)
        assert decision.domain == "transit"


class TestAgentRouterLogging:
    """Structured-log emission contract."""

    def test_emits_decision_event(
        self,
        router: AgentRouter,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(log_level="INFO")
        # Re-bind logger so it picks up the freshly configured handlers.
        get_logger("app.core.agents.router")

        router.route("Which routes are delayed?")

        captured = capsys.readouterr()
        log_lines = [line for line in captured.out.strip().splitlines() if line]
        assert log_lines, "expected at least one log line"
        decision_lines = [
            json.loads(line) for line in log_lines if '"agent.router.decision"' in line
        ]
        assert decision_lines, "expected agent.router.decision event"
        log_data = decision_lines[-1]
        assert log_data["event"] == "agent.router.decision"
        assert log_data["domain"] == "transit"
        assert isinstance(log_data["prompt_hash"], str)
        assert len(log_data["prompt_hash"]) == 12

    def test_log_does_not_contain_raw_prompt(
        self,
        router: AgentRouter,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        setup_logging(log_level="INFO")
        get_logger("app.core.agents.router")
        sentinel = "TOP_SECRET_SENTINEL_VALUE_42"

        router.route(f"Which routes are delayed? {sentinel}")

        captured = capsys.readouterr()
        assert sentinel not in captured.out


class TestSingleton:
    """``get_agent_router`` returns a process-wide singleton."""

    def test_get_agent_router_returns_same_instance(self) -> None:
        assert get_agent_router() is get_agent_router()
