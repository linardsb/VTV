"""Base Pydantic AI agent for VTV.

This module creates the foundational agent instance that all tools
(transit, obsidian) register with. The agent uses a factory pattern
so tests can create agents with TestModel.
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.core.agents.config import get_agent_model
from app.core.agents.tools.obsidian.bulk_operations import obsidian_bulk_operations
from app.core.agents.tools.obsidian.manage_folders import obsidian_manage_folders
from app.core.agents.tools.obsidian.manage_notes import obsidian_manage_notes
from app.core.agents.tools.obsidian.query_vault import obsidian_query_vault
from app.core.agents.tools.transit.check_driver_availability import check_driver_availability
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.agents.tools.transit.get_adherence_report import get_adherence_report
from app.core.agents.tools.transit.get_route_schedule import get_route_schedule
from app.core.agents.tools.transit.query_bus_status import query_bus_status
from app.core.agents.tools.transit.search_stops import search_stops
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT: str = (
    "You are a transit operations and knowledge management assistant "
    "for Riga's municipal bus system (VTV). "
    "You help dispatchers and administrators with transit queries, "
    "schedule information, operational insights, and Obsidian vault management. "
    "You can search, read, create, update, and organize notes in the user's vault. "
    "Be concise, accurate, and helpful. "
    "When you don't have enough information to answer, say so clearly. "
    "For destructive operations (delete), always confirm with the user first."
)


def create_agent(model: str | Model | None = None) -> Agent[UnifiedDeps, str]:
    """Create a Pydantic AI agent with the VTV system prompt and all tools.

    Args:
        model: LLM model to use. If None, resolves from application settings.
            Pass a TestModel instance for testing.

    Returns:
        Configured Agent instance with UnifiedDeps and string output type.
    """
    if model is None:
        model = get_agent_model()

    logger.info("agent.create_completed", model=str(model))

    return Agent(
        model,
        deps_type=UnifiedDeps,
        output_type=str,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            # Transit (5 read-only)
            query_bus_status,
            get_route_schedule,
            search_stops,
            get_adherence_report,
            check_driver_availability,
            # Obsidian vault (4)
            obsidian_query_vault,
            obsidian_manage_notes,
            obsidian_manage_folders,
            obsidian_bulk_operations,
        ],
    )


# Module-level singleton used by routes and service.
# Tests override via agent.override(model=TestModel()).
agent: Agent[UnifiedDeps, str] = create_agent()
