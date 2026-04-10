"""Transit-domain agent (AI-6.2) — 5 transit tools, full QA + correction pipeline.

``TransitAgent`` is a ``BaseAgentService`` subclass that registers ONLY the
five read-only transit tools. It mirrors ``AgentService`` structure so the
per-agent test suite can patch the same symbols the unified service tests
patch (``needs_rag``, ``MemoryService``, ``SelfCorrectionLoop``, etc.).

NOTE: every symbol patched by ``app/core/agents/tests/test_transit_agent.py``
MUST remain importable at *this* module's top level — see ``__all__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from app.core.agents.agent import build_instructions_with_skills
from app.core.agents.base import BaseAgentService, _PipelineOutcome
from app.core.agents.config import get_agent_model
from app.core.agents.context_budget import agent_budget_for
from app.core.agents.correction import CorrectedResult, SelfCorrectionLoop
from app.core.agents.pipeline import get_complex_pipeline
from app.core.agents.routing import ModelTier
from app.core.agents.skill_loader import load_skills_within_budget
from app.core.agents.tools.transit.check_driver_availability import check_driver_availability
from app.core.agents.tools.transit.deps import UnifiedDeps, create_unified_deps
from app.core.agents.tools.transit.get_adherence_report import get_adherence_report
from app.core.agents.tools.transit.get_route_schedule import get_route_schedule
from app.core.agents.tools.transit.query_bus_status import query_bus_status
from app.core.agents.tools.transit.search_stops import search_stops
from app.core.agents.tools.transit.static_store import GTFSStaticStore, get_static_store
from app.core.agents.validation import (
    ValidationContext,
    extract_tool_returns,
    validate_transit_response,
)
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.knowledge.router import needs_rag
from app.memory.bridge import persist_agent_episode
from app.memory.schemas import MemoryRecallByQueryRequest
from app.memory.service import MemoryService
from app.skills.service import SkillService

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = get_logger(__name__)


def _transit_confidence_from_warnings(warnings: list[str]) -> float:
    """Heuristic AI-6.5 confidence signal for transit responses.

    Returns 1.0 when the self-correction loop finished cleanly, 0.6 when
    warnings remain as footnotes, 0.3 when any warning contains an error-
    severity marker. Intentionally coarse — tuned once telemetry is live.
    """
    if not warnings:
        return 1.0
    has_error_marker = any("error" in w.lower() or "failed" in w.lower() for w in warnings)
    return 0.3 if has_error_marker else 0.6


TRANSIT_SYSTEM_PROMPT: str = (
    "You are a transit operations assistant for Riga's municipal bus system (VTV). "
    "You help dispatchers and administrators with real-time transit queries, "
    "schedule information, and operational insights using the 5 transit tools.\n\n"
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
    "When you don't have enough information to answer, say so clearly."
)


# Explicit re-exports — every name below is patched by the test suite via
# ``patch("app.core.agents.agents.transit.<name>", ...)``.
__all__ = [
    "TRANSIT_SYSTEM_PROMPT",
    "AsyncSessionLocal",
    "MemoryService",
    "SelfCorrectionLoop",
    "TransitAgent",
    "build_instructions_with_skills",
    "get_settings",
    "logger",
    "needs_rag",
    "persist_agent_episode",
    "transit_agent",
    "validate_transit_response",
]


def _create_transit_agent() -> Agent[UnifiedDeps, str]:
    """Build the module-level Pydantic AI agent for the transit domain.

    Registers ONLY the 5 read-only transit tools (no knowledge, no vault,
    no skills) to keep the per-request tool-docstring footprint small.
    """
    return Agent(
        get_agent_model(),
        deps_type=UnifiedDeps,
        output_type=str,
        system_prompt=TRANSIT_SYSTEM_PROMPT,
        tools=[
            query_bus_status,
            get_route_schedule,
            search_stops,
            get_adherence_report,
            check_driver_availability,
        ],
    )


# Module-level singleton — tests override via ``transit_agent.override(...)``.
transit_agent: Agent[UnifiedDeps, str] = _create_transit_agent()


class TransitAgent(BaseAgentService):
    """Transit-domain ``BaseAgentService`` subclass.

    Registers only the 5 transit tools, keeps the full QA + correction
    pipeline (route/stop existence checks, self-correction retry, complex
    pipeline dispatch), and injects GTFS static cache into validation.
    """

    agent_name: str = "transit_agent_v2"

    def __init__(self) -> None:
        """Initialize with unified deps and (optional) self-correction loop."""
        super().__init__()
        self._deps: UnifiedDeps = create_unified_deps()
        init_settings = get_settings()
        self._correction_loop: SelfCorrectionLoop | None = (
            SelfCorrectionLoop(max_rounds=init_settings.agent_max_correction_rounds)
            if init_settings.agent_self_correction_enabled
            else None
        )

    # ------------------------------------------------------------------
    # Hook: RAG routing
    # ------------------------------------------------------------------
    async def _apply_rag_routing(self, prompt: str, tier: ModelTier) -> None:
        """Disable RAG for the transit agent — no knowledge tool registered."""
        _ = prompt, tier
        self._deps.rag_enabled = False

    # ------------------------------------------------------------------
    # Hook: skill detection (flat DB skills + AI-6.4 L3 progressive pack)
    # NOTE: duplicated from AgentService; extract on AI-6.2.1
    # ------------------------------------------------------------------
    async def detect_relevant_skills(self, prompt: str) -> str:
        """Load flat DB skills + L3 progressive skills (both fail-open to '')."""
        parts: list[str] = []

        # Existing behavior: flat DB skill load.
        try:
            async with AsyncSessionLocal() as db:
                skill_service = SkillService(db)
                flat = await skill_service.get_active_skills_content()
                if flat:
                    parts.append(flat)
        except Exception:
            logger.warning("agent.skills_load_failed", exc_info=True)

        # AI-6.4: L3 progressive skill pack, gated by flag.
        if get_settings().agent_progressive_skills_enabled:
            try:
                l3 = load_skills_within_budget(
                    domain="transit",
                    prompt=prompt,
                    budget=agent_budget_for("transit"),
                )
                if l3:
                    parts.append(l3)
            except Exception:
                logger.warning("agent.l3_skills_load_failed", exc_info=True)

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Hook: memory recall block
    # NOTE: duplicated from AgentService; extract on AI-6.2.1
    # ------------------------------------------------------------------
    async def _recall_memories_block(self, prompt: str) -> str:
        """Recall relevant memories and format the ``RELEVANT MEMORIES`` block."""
        settings = get_settings()
        if not settings.memory_enabled:
            return ""
        try:
            async with AsyncSessionLocal() as memory_db:
                memory_service = MemoryService(memory_db)
                recall_request = MemoryRecallByQueryRequest(
                    query=prompt[:2000],
                    limit=settings.memory_max_recall_results,
                    min_score=settings.memory_recall_min_score,
                )
                recalled = await memory_service.recall_by_query(recall_request)

            if not recalled:
                return ""

            memory_lines = [
                f"- [{r.score:.2f}] {r.memory.content[:300]}"
                for r in recalled[: settings.memory_context_injection_limit]
            ]
            memory_context = (
                "RELEVANT MEMORIES (from prior interactions - use as context, "
                "not as authoritative facts):\n" + "\n".join(memory_lines)
            )
            logger.info(
                "agent.memory.recall_injected",
                count=len(recalled),
                top_score=recalled[0].score if recalled else 0.0,
            )
            return memory_context
        except Exception:
            logger.warning("agent.memory.recall_failed", exc_info=True)
            return ""

    # ------------------------------------------------------------------
    # Hook: system prompt assembly
    # ------------------------------------------------------------------
    def build_system_prompt(self, skills: str, memory_context: str) -> str:
        """Compose skills + memory via ``build_instructions_with_skills``."""
        return build_instructions_with_skills(skills, memory_context)

    # ------------------------------------------------------------------
    # Hook: validation cache preload (GTFS static)
    # ------------------------------------------------------------------
    async def _preload_validation_cache(self) -> GTFSStaticStore | None:
        """Pre-load the GTFS static cache (fail-open to None)."""
        if self._deps.db_session_factory is None:
            return None
        try:
            settings = get_settings()
            return await get_static_store(self._deps.db_session_factory, settings)
        except Exception:
            logger.warning("agent.validation.static_cache_unavailable", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Hook: execute (tier-routed agent invocation)
    # ------------------------------------------------------------------
    async def _execute(
        self,
        *,
        user_message: str,
        current_prompt: str,
        message_history: list[ModelMessage] | None,
        instructions: str | None,
        tier: ModelTier,
        tier_model: str | Model | None,
        static_cache: Any,  # noqa: ANN401 — GTFSStaticStore | None, typed as Any in base
    ) -> _PipelineOutcome:
        """Route to the complex pipeline, self-correction loop, or fallback."""
        if tier == "complex":
            pipeline = get_complex_pipeline(transit_agent, self._deps)
            pipeline_result = await pipeline.run(
                user_message,
                message_history=message_history,
                instructions=instructions,
                model=tier_model,
            )
            logger.info(
                "agent.pipeline.summary",
                phases_completed=pipeline_result.phases_completed,
                total_duration_ms=pipeline_result.total_duration_ms,
                phase_details=[
                    {"name": pd.name, "duration_ms": pd.duration_ms, "status": pd.status}
                    for pd in pipeline_result.phase_details
                ],
            )
            return _PipelineOutcome(
                response_text=pipeline_result.output,
                warnings=[],
                messages=[],
                confidence=0.9,
                tools_used=(),
            )

        if self._correction_loop is not None:
            corrected: CorrectedResult = await self._correction_loop.run_with_correction(
                transit_agent,
                user_message,
                deps=self._deps,
                message_history=message_history,
                instructions=instructions,
                model=tier_model,
                static_cache=static_cache,
            )
            persist_agent_episode(
                agent_name=self.agent_name,
                prompt=current_prompt,
                response=corrected.output,
                messages=corrected.all_messages,
            )
            corrected_confidence = _transit_confidence_from_warnings(corrected.warnings)
            corrected_tools = tuple(
                rec.tool_name for rec in extract_tool_returns(corrected.all_messages)
            )
            return _PipelineOutcome(
                response_text=corrected.output,
                warnings=corrected.warnings,
                messages=corrected.all_messages,
                confidence=corrected_confidence,
                tools_used=corrected_tools,
            )

        result = await transit_agent.run(
            user_message,
            deps=self._deps,
            message_history=message_history,
            instructions=instructions,
            model=tier_model,
        )
        fallback_messages = list(result.all_messages())

        persist_agent_episode(
            agent_name=self.agent_name,
            prompt=current_prompt,
            response=result.output,
            messages=fallback_messages,
        )
        fallback_tools = tuple(rec.tool_name for rec in extract_tool_returns(fallback_messages))
        return _PipelineOutcome(
            response_text=result.output,
            warnings=None,  # signal _post_process to run QA itself
            messages=fallback_messages,
            confidence=None,  # QA hasn't run yet; leave re-route gate disabled
            tools_used=fallback_tools,
        )

    # ------------------------------------------------------------------
    # Hook: post-process QA (transit validator)
    # ------------------------------------------------------------------
    def _run_qa(
        self,
        *,
        response: str,
        current_prompt: str,
        messages: list[ModelMessage],
        static_cache: Any,  # noqa: ANN401
    ) -> list[str]:
        """Delegate to ``validate_transit_response`` via the module namespace."""
        ctx = ValidationContext(
            user_message=current_prompt,
            static_cache=static_cache,
            tool_returns=extract_tool_returns(messages),
        )
        validation = validate_transit_response(response, ctx)
        return list(validation.warnings)

    async def close(self) -> None:
        """Close HTTP clients used by agent tools."""
        try:
            await self._deps.transit_http_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed during shutdown
        try:
            await self._deps.obsidian_http_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed during shutdown
