"""Knowledge-domain agent (AI-6.2) — single RAG search tool.

``KnowledgeAgent`` registers ONLY the ``search_knowledge_base`` tool. RAG is
always enabled for this agent (no router gate). No self-correction loop, no
complex-tier dispatch, no GTFS validation cache — the knowledge domain has
its own grounding rules enforced by the system prompt + search confidence
threshold inside the tool.

NOTE: every symbol patched by ``app/core/agents/tests/test_knowledge_agent.py``
MUST remain importable at *this* module's top level — see ``__all__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from app.core.agents.agent import build_instructions_with_skills
from app.core.agents.base import BaseAgentService, _PipelineOutcome
from app.core.agents.config import get_agent_model
from app.core.agents.routing import ModelTier
from app.core.agents.tools.knowledge.search_knowledge import search_knowledge_base
from app.core.agents.tools.transit.deps import UnifiedDeps, create_unified_deps
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.memory.bridge import persist_agent_episode
from app.memory.schemas import MemoryRecallByQueryRequest
from app.memory.service import MemoryService

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = get_logger(__name__)


KNOWLEDGE_SYSTEM_PROMPT: str = (
    "You are an organizational knowledge assistant for VTV (Riga's municipal "
    "bus system). You answer questions by searching the internal knowledge "
    "base of policies, compliance documents, legal materials, driver records, "
    "and internal communications.\n\n"
    #
    # --- Language ---
    #
    "LANGUAGE RULES:\n"
    "- ALWAYS respond in Latvian (latviešu valoda) by default.\n"
    "- Use proper Latvian diacritics (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž).\n"
    "- If the user writes in English, respond in English.\n"
    "- Tool outputs may be in either language - preserve original terminology "
    "when citing but write your own prose in the user's language.\n\n"
    #
    # --- Tool usage ---
    #
    "TOOL USAGE:\n"
    "- Use ``search_knowledge_base`` for EVERY factual question. Do not guess.\n"
    "- Pass a focused natural-language query in the user's language.\n"
    "- Prefer one well-formed search over many narrow ones.\n\n"
    #
    # --- Grounding rules ---
    #
    "GROUNDING RULES (CRITICAL):\n"
    "- If the tool returns 'No relevant documents found', tell the user "
    "honestly: 'I don't know' (Latvian: 'Nezinu') and suggest rephrasing or "
    "uploading the relevant document.\n"
    "- Do NOT fabricate, guess, or extrapolate beyond what the search results "
    "contain.\n"
    "- If you are not certain, say 'I don't know' explicitly rather than "
    "speculating.\n\n"
    #
    # --- Citations ---
    #
    "CITATION RULES:\n"
    "- ALWAYS cite knowledge base results as clickable links.\n"
    "- Format (Latvian): [title](/lv/documents/{document_id})\n"
    "- Format (English): [title](/en/documents/{document_id})\n"
    "- Use the document_id from the search result to construct the link.\n"
    "- Place inline citations in the body AND a 'Sources' list at the end of "
    "every response that cites search results.\n"
    "- Example (Latvian): Saskaņā ar "
    "[Vadītāju rokasgrāmatu](/lv/documents/42) ...\n"
    "- Example (English): According to the "
    "[Driver Handbook](/en/documents/42) ...\n\n"
    "Sources:\n"
    "- [Vadītāju rokasgrāmata](/lv/documents/42)\n"
)


# Explicit re-exports — every name below is patched by the test suite.
__all__ = [
    "KNOWLEDGE_SYSTEM_PROMPT",
    "AsyncSessionLocal",
    "KnowledgeAgent",
    "MemoryService",
    "build_instructions_with_skills",
    "get_settings",
    "knowledge_agent",
    "logger",
    "persist_agent_episode",
]


def _create_knowledge_agent() -> Agent[UnifiedDeps, str]:
    """Build the module-level Pydantic AI agent for the knowledge domain."""
    return Agent(
        get_agent_model(),
        deps_type=UnifiedDeps,
        output_type=str,
        system_prompt=KNOWLEDGE_SYSTEM_PROMPT,
        tools=[search_knowledge_base],
    )


# Module-level singleton — tests override via ``knowledge_agent.override(...)``.
knowledge_agent: Agent[UnifiedDeps, str] = _create_knowledge_agent()


class KnowledgeAgent(BaseAgentService):
    """Knowledge-domain ``BaseAgentService`` subclass.

    Registers only the knowledge base search tool. RAG is always enabled.
    No self-correction loop, no complex-tier branching — the single-tool
    surface makes these unnecessary and the QA layer doesn't apply.
    """

    agent_name: str = "knowledge_agent"

    def __init__(self) -> None:
        """Initialize with unified deps for the knowledge search tool."""
        super().__init__()
        self._deps: UnifiedDeps = create_unified_deps()

    # ------------------------------------------------------------------
    # Hook: RAG routing — always enable for the knowledge agent
    # ------------------------------------------------------------------
    async def _apply_rag_routing(self, prompt: str, tier: ModelTier) -> None:
        """Always enable RAG — this agent exists to query the knowledge base."""
        _ = prompt, tier
        self._deps.rag_enabled = True

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
    # Hook: execute — single branch, no tier dispatch
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
        static_cache: Any,  # noqa: ANN401 — unused here, base signature
    ) -> _PipelineOutcome:
        """Invoke ``knowledge_agent`` and persist the episode."""
        _ = tier, static_cache
        result = await knowledge_agent.run(
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
        return _PipelineOutcome(
            response_text=result.output,
            warnings=[],  # signal _post_process: no QA, no footnotes
            messages=fallback_messages,
        )

    # ------------------------------------------------------------------
    # Hook: _run_qa — no transit validation for knowledge responses
    # ------------------------------------------------------------------
    def _run_qa(
        self,
        *,
        response: str,
        current_prompt: str,
        messages: list[ModelMessage],
        static_cache: Any,  # noqa: ANN401
    ) -> list[str]:
        """Return an empty list — the knowledge agent does not run transit QA."""
        _ = response, current_prompt, messages, static_cache
        return []

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
