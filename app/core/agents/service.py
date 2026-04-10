"""Transit-domain agent service — wires the BaseAgentService harness.

``AgentService`` is a thin subclass of ``BaseAgentService`` that overrides
the hooks that touch transit-specific dependencies (RAG router, GTFS static
cache, memory recall, self-correction loop, complex pipeline, transit
validator).

NOTE: every symbol patched by ``app/core/agents/tests/test_service.py`` MUST
remain importable at *this* module's top level. The test suite patches these
via ``patch("app.core.agents.service.<name>", ...)`` and relies on Python's
attribute-binding semantics to intercept calls. Do not remove re-exports
even if pyflakes claims they are unused — the ``# noqa: F401`` comments
document that constraint.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import ModelMessage

from app.core.agents.agent import agent, build_instructions_with_skills
from app.core.agents.base import BaseAgentService, _PipelineOutcome
from app.core.agents.config import resolve_tier_model
from app.core.agents.correction import CorrectedResult, SelfCorrectionLoop
from app.core.agents.pipeline import get_complex_pipeline
from app.core.agents.routing import (
    ModelTier,
    classify_prompt,
)
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from app.core.agents.tools.transit.deps import UnifiedDeps, create_unified_deps
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


# Explicit re-exports — every name below is patched by the test suite via
# ``patch("app.core.agents.service.<name>", ...)``. Removing any entry breaks
# ``app/core/agents/tests/test_service.py``.
__all__ = [
    "AgentService",
    "AsyncSessionLocal",
    "CorrectedResult",
    "MemoryService",
    "SelfCorrectionLoop",
    "SkillService",
    "agent",
    "build_instructions_with_skills",
    "classify_prompt",
    "close_agent_service",
    "extract_tool_returns",
    "get_agent_service",
    "get_complex_pipeline",
    "get_settings",
    "logger",
    "needs_rag",
    "persist_agent_episode",
    "resolve_tier_model",
    "validate_transit_response",
]


class AgentService(BaseAgentService):
    """Orchestrates transit agent chat interactions.

    Concrete subclass of ``BaseAgentService`` that wires the transit agent,
    the GTFS static cache, the self-correction loop, the complex-tier
    pipeline, and the VTV memory/skills infrastructure.
    """

    agent_name: str = "transit_agent"

    def __init__(self) -> None:
        """Initialize with unified dependencies for agent tool execution."""
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
        """Toggle ``self._deps.rag_enabled`` from the knowledge router."""
        settings = get_settings()
        if settings.knowledge_router_enabled:
            rag_decision = needs_rag(prompt)
            self._deps.rag_enabled = rag_decision.needs_rag
            logger.info(
                "agent.rag_routing",
                needs_rag=rag_decision.needs_rag,
                rag_score=rag_decision.rag_score,
                skip_score=rag_decision.skip_score,
                tier=tier,
            )
        else:
            self._deps.rag_enabled = True

    # ------------------------------------------------------------------
    # Hook: skill detection
    # ------------------------------------------------------------------
    async def detect_relevant_skills(self, prompt: str) -> str:
        """Load all active skills from the DB (fail-open to '')."""
        _ = prompt  # skills loader returns all active skills regardless of prompt
        try:
            async with AsyncSessionLocal() as db:
                skill_service = SkillService(db)
                return await skill_service.get_active_skills_content()
        except Exception:
            logger.warning("agent.skills_load_failed", exc_info=True)
            return ""

    # ------------------------------------------------------------------
    # Hook: memory recall block
    # ------------------------------------------------------------------
    async def _recall_memories_block(self, prompt: str) -> str:
        """Recall relevant memories and format the ``RELEVANT MEMORIES`` block.

        Byte-identical to the original ``service.py:177-205`` block — the
        ``test_service.py`` suite asserts on the exact prefix, score
        formatting, and 300-char content truncation.
        """
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
        """Compose skills + memory via ``build_instructions_with_skills``.

        Overridden so ``test_service.py`` can patch
        ``app.core.agents.service.build_instructions_with_skills``.
        """
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
        """Route to the complex pipeline, self-correction loop, or fallback.

        Mirrors the behavior of the original ``AgentService.chat`` lines
        223-287: complex tier runs the orchestrator; standard tier runs the
        self-correction loop when enabled; otherwise a plain ``agent.run``
        with fire-and-forget memory bridge persistence.
        """
        if tier == "complex":
            pipeline = get_complex_pipeline(agent, self._deps)
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
            # Complex path: no QA footnotes, no memory persist (existing behavior).
            return _PipelineOutcome(
                response_text=pipeline_result.output,
                warnings=[],
                messages=[],
            )

        if self._correction_loop is not None:
            corrected: CorrectedResult = await self._correction_loop.run_with_correction(
                agent,
                user_message,
                deps=self._deps,
                message_history=message_history,
                instructions=instructions,
                model=tier_model,
                static_cache=static_cache,
            )
            # Memory persistence uses the FINAL attempt's messages.
            persist_agent_episode(
                agent_name=self.agent_name,
                prompt=current_prompt,
                response=corrected.output,
                messages=corrected.all_messages,
            )
            return _PipelineOutcome(
                response_text=corrected.output,
                warnings=corrected.warnings,
                messages=corrected.all_messages,
            )

        result = await agent.run(
            user_message,
            deps=self._deps,
            message_history=message_history,
            instructions=instructions,
            model=tier_model,
        )
        fallback_messages = list(result.all_messages())

        # Fire-and-forget: persist multi-tool episodes as memory.
        persist_agent_episode(
            agent_name=self.agent_name,
            prompt=current_prompt,
            response=result.output,
            messages=fallback_messages,
        )
        return _PipelineOutcome(
            response_text=result.output,
            warnings=None,  # signal _post_process to run QA itself
            messages=fallback_messages,
        )

    # ------------------------------------------------------------------
    # Hook: post-process (re-run QA via service-module validate helper)
    # ------------------------------------------------------------------
    def _run_qa(
        self,
        *,
        response: str,
        current_prompt: str,
        messages: list[ModelMessage],
        static_cache: Any,  # noqa: ANN401
    ) -> list[str]:
        """Delegate to ``validate_transit_response`` via the service module.

        Overridden so ``test_service.py`` could patch the transit validator
        through ``app.core.agents.service.validate_transit_response`` if it
        ever needed to.
        """
        ctx = ValidationContext(
            user_message=current_prompt,
            static_cache=static_cache,
            tool_returns=extract_tool_returns(messages),
        )
        validation = validate_transit_response(response, ctx)
        return list(validation.warnings)

    # ------------------------------------------------------------------
    # Hook: response assembly (overridden so tests can patch get_settings)
    # ------------------------------------------------------------------
    def _build_response(
        self,
        *,
        content: str,
        tier_model: str | Model | None,
    ) -> ChatCompletionResponse:
        """Assemble the OpenAI-compatible response envelope."""
        settings = get_settings()
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        model_name = (
            str(tier_model)
            if tier_model is not None
            else f"{settings.llm_provider}:{settings.llm_model}"
        )
        return ChatCompletionResponse(
            id=response_id,
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(),
        )

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


# --- Module-level singleton -------------------------------------------------

_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """Get or create the agent service singleton.

    Reuses the same ``httpx.AsyncClient`` across requests for connection pooling.

    Returns:
        Singleton ``AgentService`` instance.
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


async def close_agent_service() -> None:
    """Close the singleton agent service and its HTTP client.

    Called during application shutdown.
    """
    global _agent_service
    if _agent_service is not None:
        await _agent_service.close()
        _agent_service = None
