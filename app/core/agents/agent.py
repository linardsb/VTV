"""Base Pydantic AI agent for VTV.

This module creates the foundational agent instance that all future
tools (transit, obsidian) will register with. The agent uses a factory
pattern so tests can create agents with TestModel.
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.core.agents.config import get_agent_model
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT: str = (
    "You are a transit operations and knowledge management assistant "
    "for Riga's municipal bus system (VTV). "
    "You help dispatchers and administrators with transit queries, "
    "schedule information, and operational insights. "
    "Be concise, accurate, and helpful. "
    "When you don't have enough information to answer, say so clearly."
)


def create_agent(model: str | Model | None = None) -> Agent[None, str]:
    """Create a Pydantic AI agent with the VTV system prompt.

    Args:
        model: LLM model to use. If None, resolves from application settings.
            Pass a TestModel instance for testing.

    Returns:
        Configured Agent instance with string output type.
    """
    if model is None:
        model = get_agent_model()

    logger.info("agent.create_completed", model=str(model))

    return Agent(
        model,
        output_type=str,
        system_prompt=SYSTEM_PROMPT,
    )


# Module-level singleton used by routes and service.
# Tests override via agent.override(model=TestModel()).
agent: Agent[None, str] = create_agent()
