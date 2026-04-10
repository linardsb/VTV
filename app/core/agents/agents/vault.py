"""Vault-domain agent (AI-6.2) — 4 Obsidian vault tools.

``VaultAgent`` registers the 4 Obsidian tools (query, notes, folders, bulk
operations). RAG is disabled (no knowledge tool), self-correction is not
applicable (no transit validator), and the system prompt enforces a
confirm-before-destructive rule as defense-in-depth on top of the tool-level
``confirm: true`` enforcement.

NOTE: every symbol patched by ``app/core/agents/tests/test_vault_agent.py``
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
from app.core.agents.routing import ModelTier
from app.core.agents.skill_loader import load_skills_within_budget
from app.core.agents.tools.obsidian.bulk_operations import obsidian_bulk_operations
from app.core.agents.tools.obsidian.manage_folders import obsidian_manage_folders
from app.core.agents.tools.obsidian.manage_notes import obsidian_manage_notes
from app.core.agents.tools.obsidian.query_vault import obsidian_query_vault
from app.core.agents.tools.transit.deps import UnifiedDeps, create_unified_deps
from app.core.agents.validation import extract_tool_returns
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.memory.bridge import persist_agent_episode
from app.memory.schemas import MemoryRecallByQueryRequest
from app.memory.service import MemoryService

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = get_logger(__name__)


VAULT_SYSTEM_PROMPT: str = (
    "You are an Obsidian vault assistant for VTV. You help users search, "
    "read, create, update, and organize notes in the operational Obsidian "
    "vault using the 4 vault tools.\n\n"
    #
    # --- Language ---
    #
    "LANGUAGE RULES:\n"
    "- ALWAYS respond in Latvian (latviešu valoda) by default.\n"
    "- Use proper Latvian diacritics (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž).\n"
    "- If the user writes in English, respond in English.\n"
    "- Note contents are preserved verbatim; match the user's language in "
    "your own prose.\n\n"
    #
    # --- Tool usage ---
    #
    "TOOL USAGE:\n"
    "- Use ``obsidian_query_vault`` FIRST to locate notes before editing. "
    "Prefer tag/glob/search lookups over manual path guessing.\n"
    "- Use ``obsidian_manage_notes`` for CRUD on a single note (create, "
    "read, update, frontmatter, section edits).\n"
    "- Use ``obsidian_manage_folders`` for folder CRUD.\n"
    "- Use ``obsidian_bulk_operations`` for batch moves/renames/deletes. "
    "ALWAYS pass ``dry_run=true`` on the FIRST call so the user can preview "
    "the planned changes before anything is written.\n\n"
    #
    # --- Frontmatter conventions ---
    #
    "FRONTMATTER CONVENTIONS:\n"
    "- Every note MUST have YAML frontmatter at the top.\n"
    "- Required fields: ``title`` (string), ``tags`` (list of strings in "
    "kebab-case, e.g. ``transit-ops``), ``created`` (ISO-8601 date), "
    "``updated`` (ISO-8601 date).\n"
    "- When creating notes, generate valid frontmatter automatically.\n"
    "- When editing notes, bump ``updated`` to today's date.\n\n"
    #
    # --- Safe deletion clause (SECURITY) ---
    #
    "DESTRUCTIVE OPERATIONS (CRITICAL):\n"
    "- For ANY destructive operation (delete folder, bulk delete, bulk move "
    "across folders), FIRST respond with a plain-text preview of what will "
    "be changed and ASK 'Confirm deletion? (yes/no)' before passing "
    "``confirm=true`` to the tool.\n"
    "- NEVER delete on the first turn of a conversation unless the user's "
    "message already contains an explicit 'confirm' or 'yes'.\n"
    "- For ``obsidian_bulk_operations``, ALWAYS run with ``dry_run=true`` "
    "first and show the preview before executing with ``dry_run=false``.\n"
    "- If in doubt, ask. A missed delete is better than a wrong delete.\n\n"
    "When you don't have enough information to answer, say so clearly."
)


# Explicit re-exports — every name below is patched by the test suite.
__all__ = [
    "VAULT_SYSTEM_PROMPT",
    "AsyncSessionLocal",
    "MemoryService",
    "VaultAgent",
    "build_instructions_with_skills",
    "get_settings",
    "logger",
    "persist_agent_episode",
    "vault_agent",
]


def _create_vault_agent() -> Agent[UnifiedDeps, str]:
    """Build the module-level Pydantic AI agent for the vault domain."""
    return Agent(
        get_agent_model(),
        deps_type=UnifiedDeps,
        output_type=str,
        system_prompt=VAULT_SYSTEM_PROMPT,
        tools=[
            obsidian_query_vault,
            obsidian_manage_notes,
            obsidian_manage_folders,
            obsidian_bulk_operations,
        ],
    )


# Module-level singleton — tests override via ``vault_agent.override(...)``.
vault_agent: Agent[UnifiedDeps, str] = _create_vault_agent()


class VaultAgent(BaseAgentService):
    """Vault-domain ``BaseAgentService`` subclass.

    Registers only the 4 Obsidian tools. RAG disabled. No self-correction
    loop. Safe-delete enforced by the system prompt on top of the tool-level
    ``confirm`` enforcement.
    """

    agent_name: str = "vault_agent"

    def __init__(self) -> None:
        """Initialize with unified deps for the vault tools."""
        super().__init__()
        self._deps: UnifiedDeps = create_unified_deps()

    # ------------------------------------------------------------------
    # Hook: RAG routing
    # ------------------------------------------------------------------
    async def _apply_rag_routing(self, prompt: str, tier: ModelTier) -> None:
        """Disable RAG — no knowledge tool registered on the vault agent."""
        _ = prompt, tier
        self._deps.rag_enabled = False

    # ------------------------------------------------------------------
    # Hook: skill detection (AI-6.4 L3 progressive pack only)
    # ------------------------------------------------------------------
    async def detect_relevant_skills(self, prompt: str) -> str:
        """Load the L3 progressive skill pack for the vault domain."""
        if not get_settings().agent_progressive_skills_enabled:
            return ""
        try:
            return load_skills_within_budget(
                domain="vault",
                prompt=prompt,
                budget=agent_budget_for("vault"),
            )
        except Exception:
            logger.warning("agent.l3_skills_load_failed", exc_info=True)
            return ""

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
        """Invoke ``vault_agent`` and persist the episode."""
        _ = tier, static_cache
        result = await vault_agent.run(
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
        tools_used = tuple(rec.tool_name for rec in extract_tool_returns(fallback_messages))
        # Vault tools are deterministic file ops — the only confidence signal
        # is whether the response carries QA warnings. Empty list here means
        # "no warnings", so fall back to 1.0; AI-6.5 never re-routes on 1.0.
        return _PipelineOutcome(
            response_text=result.output,
            warnings=[],  # signal _post_process: no QA, no footnotes
            messages=fallback_messages,
            confidence=1.0,
            tools_used=tools_used,
        )

    # ------------------------------------------------------------------
    # Hook: _run_qa — no transit validation for vault responses
    # ------------------------------------------------------------------
    def _run_qa(
        self,
        *,
        response: str,
        current_prompt: str,
        messages: list[ModelMessage],
        static_cache: Any,  # noqa: ANN401
    ) -> list[str]:
        """Return an empty list — the vault agent does not run transit QA."""
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
