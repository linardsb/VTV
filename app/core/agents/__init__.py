"""AI agent infrastructure for VTV.

This module provides the base Pydantic AI agent, configuration,
schemas, and API routes for the unified agent service.
"""

from app.core.agents.agent_result import VALID_DOMAINS, AgentResult
from app.core.agents.context_budget import AGENT_BUDGETS, ContextBudget, agent_budget_for

__all__ = [
    "AGENT_BUDGETS",
    "VALID_DOMAINS",
    "AgentResult",
    "ContextBudget",
    "agent_budget_for",
]
