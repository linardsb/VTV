"""Per-agent context budgets for AI-6.4 progressive skill loading.

Each agent owns a ``ContextBudget`` that caps how many tokens the progressive
skill loader (``skill_loader.load_skills_within_budget``) may spend injecting
L3 skills into the system prompt. The default budget is conservative; domain
agents override ``skill_docs_max`` based on tool-output density.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Token caps for the agent's prompt-composition pipeline.

    Attributes:
        system_prompt_max: Cap for the base system prompt section.
        skill_docs_max: Cap for the progressive skill docs section (AI-6.4).
        memory_max: Cap for the recalled memories block.
        user_message_max: Cap for the user-turn message body.
        total_max: Overall ceiling across all sections combined.
    """

    system_prompt_max: int = 3000
    skill_docs_max: int = 2000
    memory_max: int = 1500
    user_message_max: int = 3000
    total_max: int = 10000


AGENT_BUDGETS: Final[dict[str, ContextBudget]] = {
    "transit": ContextBudget(skill_docs_max=2500),
    "knowledge": ContextBudget(skill_docs_max=2000),
    "vault": ContextBudget(skill_docs_max=1500),
    "unified": ContextBudget(skill_docs_max=3000),
}


def agent_budget_for(agent_name: str) -> ContextBudget:
    """Return the ``ContextBudget`` for an agent, falling back to defaults.

    Args:
        agent_name: Domain agent name (``transit``, ``knowledge``, ``vault``,
            ``unified``). Unknown names yield the default ``ContextBudget()``.

    Returns:
        The registered budget or ``ContextBudget()`` defaults if unknown.
    """
    return AGENT_BUDGETS.get(agent_name, ContextBudget())


__all__ = ["AGENT_BUDGETS", "ContextBudget", "agent_budget_for"]
