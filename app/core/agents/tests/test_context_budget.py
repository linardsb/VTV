"""Tests for ``app.core.agents.context_budget`` (AI-6.4)."""

# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import dataclasses

import pytest

from app.core.agents.context_budget import AGENT_BUDGETS, ContextBudget, agent_budget_for


def test_context_budget_is_frozen() -> None:
    """``ContextBudget`` instances must be immutable."""
    budget = ContextBudget()
    with pytest.raises(dataclasses.FrozenInstanceError):
        budget.skill_docs_max = 9999  # type: ignore[misc]


def test_context_budget_default_values() -> None:
    """Defaults match the AI-6.4 spec."""
    budget = ContextBudget()
    assert budget.system_prompt_max == 3000
    assert budget.skill_docs_max == 2000
    assert budget.memory_max == 1500
    assert budget.user_message_max == 3000
    assert budget.total_max == 10000


def test_agent_budget_for_transit_has_overridden_skill_cap() -> None:
    assert agent_budget_for("transit").skill_docs_max == 2500


def test_agent_budget_for_knowledge_matches_default_cap() -> None:
    assert agent_budget_for("knowledge").skill_docs_max == 2000


def test_agent_budget_for_unknown_falls_back_to_defaults() -> None:
    """Unknown agents get the default ``ContextBudget()``."""
    budget = agent_budget_for("unknown-agent")
    assert budget == ContextBudget()
    assert budget.skill_docs_max == 2000


def test_all_registered_budgets_are_context_budgets() -> None:
    """Every entry in ``AGENT_BUDGETS`` is a ``ContextBudget``."""
    for name, budget in AGENT_BUDGETS.items():
        assert isinstance(budget, ContextBudget), name
