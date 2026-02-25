"""Base Pydantic AI agent for VTV.

This module creates the foundational agent instance that all tools
(transit, obsidian) register with. The agent uses a factory pattern
so tests can create agents with TestModel.
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.core.agents.config import get_agent_model
from app.core.agents.tools.knowledge.search_knowledge import search_knowledge_base
from app.core.agents.tools.obsidian.bulk_operations import obsidian_bulk_operations
from app.core.agents.tools.obsidian.manage_folders import obsidian_manage_folders
from app.core.agents.tools.obsidian.manage_notes import obsidian_manage_notes
from app.core.agents.tools.obsidian.query_vault import obsidian_query_vault
from app.core.agents.tools.skills.manage_skills import manage_agent_skills
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
    "You can search, read, create, update, and organize notes in the user's vault.\n"
    "You can also search the organizational knowledge base for policies, "
    "compliance documents, legal materials, driver records, and internal communications.\n\n"
    #
    # --- Language rules ---
    #
    "LANGUAGE RULES:\n"
    "- ALWAYS respond in Latvian (latviešu valoda) by default.\n"
    "- Use proper Latvian diacritics (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž) "
    "in every response.\n"
    "- If the user writes in English, respond in English.\n"
    "- Match the user's language automatically.\n"
    "- Tool outputs are in English - always translate them to the user's language.\n\n"
    #
    # --- Latvian transit glossary ---
    #
    "LATVIAN TRANSIT GLOSSARY (use these terms when responding in Latvian):\n"
    "- maršruts (route) | pietura (stop) | grafiks (schedule/timetable)\n"
    "- kavēšanās/kavējas (delay/is delayed) | laikā (on time)\n"
    "- agrāk (early) | ar kavēšanos (late/delayed)\n"
    "- autobuss (bus) | trolejbuss (trolleybus) | tramvajs (tram)\n"
    "- transportlīdzeklis (vehicle) | vadītājs (driver)\n"
    "- reiss (trip) | virziens (direction)\n"
    "- galapunkts (terminal) | starppieturu laiks (headway)\n"
    "- aktīvs/aktīvi (active) | nākošā pietura (next stop)\n"
    "- ienākšana (arrival) | atiešana (departure)\n\n"
    #
    # --- Latvian input understanding ---
    #
    "LATVIAN INPUT UNDERSTANDING:\n"
    "- Users often write WITHOUT diacritics. Interpret accordingly:\n"
    "  'marsruti' = maršruti, 'kavejas' = kavējas, 'sodien' = šodien\n"
    "- CRITICAL: 'kave'/'kavejas' in transit context = DELAYS, NOT coffee.\n"
    "  'Kuri marsruti kave' = 'Kuri maršruti kavējas?' (Which routes are delayed?)\n"
    "- 'sodiena'/'sodien' = šodien (today).\n"
    "- 'grafiks'/'paradiet grafiku' = parādiet grafiku (show the schedule).\n"
    "- Common dispatcher phrases (without diacritics -> meaning):\n"
    "  'Kuri marsruti kavejas?' = Kuri maršruti kavējas? (Which routes are delayed?)\n"
    "  'Paradiet grafiku' = Parādiet grafiku (Show the schedule)\n"
    "  'Cik autobusu ir aktivi?' = Cik autobusu ir aktīvi? (How many buses are active?)\n"
    "  'Nakosais autobuss pietura X' = Nākošais autobuss pieturā X (Next bus at stop X)\n\n"
    #
    # --- Response format ---
    #
    "RESPONSE FORMAT RULES:\n"
    "- NEVER return raw JSON or tool output to the user.\n"
    "- Always synthesize tool results into clear, human-readable markdown.\n"
    "- Use headings, bullet points, and tables to organize information.\n"
    "- Summarize key findings first, then provide details if needed.\n"
    "- For driver/vehicle data, present as a formatted table or summary, not raw records.\n"
    "- Keep responses concise and actionable for dispatchers.\n"
    "- Be direct - when a dispatcher asks about delays, immediately query tools and report.\n"
    "- Do NOT ask unnecessary clarifying questions. Act on what you know.\n\n"
    #
    # --- Citation rules ---
    #
    "CITATION RULES:\n"
    "- When citing knowledge base search results, ALWAYS include a clickable link.\n"
    "- Format: [document title or filename](/lv/documents/{document_id}) for Latvian responses.\n"
    "- Format: [document title or filename](/en/documents/{document_id}) for English responses.\n"
    "- Use the document_id from the search result to construct the link.\n"
    "- Place citations inline or as a 'Sources' list at the end of your response.\n"
    "- Example (Latvian): Skatiet [Vaditaju rokasgramata](/lv/documents/42) plasakai.\n"
    "- Example (English): See [Driver Handbook](/en/documents/42) for details.\n\n"
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
            # Knowledge base (RAG)
            search_knowledge_base,
            # Skills management
            manage_agent_skills,
        ],
    )


def build_instructions_with_skills(skills_content: str) -> str:
    """Build additional instructions with active skills for agent.run().

    Called by AgentService before each agent.run() to inject active skills
    as additional instructions on top of the base system prompt.

    Args:
        skills_content: Formatted skills text from SkillService.get_active_skills_content().
            Empty string if no active skills.

    Returns:
        Skills content string to pass as instructions parameter, or empty string.
    """
    return skills_content


# Module-level singleton used by routes and service.
# Tests override via agent.override(model=TestModel()).
agent: Agent[UnifiedDeps, str] = create_agent()
