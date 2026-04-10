"""Tests for ``app.core.agents.agents.vault.VaultAgent`` (AI-6.2)."""

# pyright: reportPrivateUsage=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.core.agents.agents.vault import (
    VAULT_SYSTEM_PROMPT,
    VaultAgent,
    vault_agent,
)
from app.core.agents.exceptions import AgentExecutionError
from app.core.agents.schemas import ChatCompletionRequest, ChatMessage
from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.config import get_settings
from app.memory.schemas import MemoryEntryResponse, MemoryRecallResponse
from app.shared.models import utcnow

# Prevent accidental real LLM API calls during testing.
models.ALLOW_MODEL_REQUESTS = False


def _make_request(text: str = "Find my notes about transit ops") -> ChatCompletionRequest:
    return ChatCompletionRequest(messages=[ChatMessage(role="user", content=text)])


def _create_vault_agent_service() -> VaultAgent:
    """Build a VaultAgent with mocked HTTP deps."""
    with patch("app.core.agents.agents.vault.create_unified_deps") as mock_deps:
        mock_deps.return_value = UnifiedDeps(
            transit_http_client=AsyncMock(spec=httpx.AsyncClient),
            obsidian_http_client=AsyncMock(spec=httpx.AsyncClient),
            settings=get_settings(),
            db_session_factory=None,
            rag_enabled=True,
        )
        return VaultAgent()


def _make_recall_responses(count: int = 1) -> list[MemoryRecallResponse]:
    now = utcnow()
    out: list[MemoryRecallResponse] = []
    for i in range(count):
        entry = MemoryEntryResponse(
            id=i + 1,
            agent_type="vault",
            memory_type="semantic",
            content=f"Vault memory {i + 1}",
            metadata_json=None,
            decay_weight=1.0,
            is_evergreen=False,
            source="agent",
            recalled_count=0,
            created_at=now,
            updated_at=now,
        )
        out.append(MemoryRecallResponse(memory=entry, score=0.9 - i * 0.1))
    return out


def _settings_mock() -> MagicMock:
    settings_obj = MagicMock()
    settings_obj.memory_enabled = False
    settings_obj.agent_self_correction_enabled = False
    settings_obj.llm_provider = "test"
    settings_obj.llm_model = "test-model"
    return settings_obj


# --- 1. agent_name ----------------------------------------------------------


def test_agent_name_is_vault_agent() -> None:
    svc = _create_vault_agent_service()
    assert svc.agent_name == "vault_agent"


# --- 2. Tool set is exactly the 4 obsidian tools ---------------------------


def test_tool_set_has_4_obsidian_tools() -> None:
    tools = vault_agent._function_toolset.tools
    expected = {
        "obsidian_query_vault",
        "obsidian_manage_notes",
        "obsidian_manage_folders",
        "obsidian_bulk_operations",
    }
    assert set(tools.keys()) == expected


# --- 3. Tool set excludes manage_skills ------------------------------------


def test_tool_set_excludes_manage_skills() -> None:
    tools = vault_agent._function_toolset.tools
    assert "manage_agent_skills" not in tools


# --- 4. Tool set excludes search_knowledge_base ----------------------------


def test_tool_set_excludes_search_knowledge_base() -> None:
    tools = vault_agent._function_toolset.tools
    assert "search_knowledge_base" not in tools


# --- 5. RAG routing disables RAG -------------------------------------------


@pytest.mark.asyncio
async def test_apply_rag_routing_disables_rag() -> None:
    svc = _create_vault_agent_service()
    svc._deps.rag_enabled = True
    await svc._apply_rag_routing("any", "standard")
    assert svc._deps.rag_enabled is False


# --- 6. _run_qa returns empty list -----------------------------------------


def test_run_qa_returns_empty_list() -> None:
    svc = _create_vault_agent_service()
    result = svc._run_qa(
        response="done",
        current_prompt="test",
        messages=[],
        static_cache=None,
    )
    assert result == []


# --- 7. Memory enabled returns formatted recall block ---------------------


@pytest.mark.asyncio
async def test_recall_memories_block_when_memory_enabled() -> None:
    svc = _create_vault_agent_service()
    mock_memory_svc = AsyncMock()
    mock_memory_svc.recall_by_query.return_value = _make_recall_responses(1)

    with patch("app.core.agents.agents.vault.MemoryService", return_value=mock_memory_svc):
        with patch("app.core.agents.agents.vault.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.memory_enabled = True
            settings_obj.memory_max_recall_results = 5
            settings_obj.memory_recall_min_score = 0.5
            settings_obj.memory_context_injection_limit = 10
            mock_settings.return_value = settings_obj
            result = await svc._recall_memories_block("test")

    assert result.startswith("RELEVANT MEMORIES")
    assert "[0.90]" in result


# --- 8. Memory disabled returns empty --------------------------------------


@pytest.mark.asyncio
async def test_recall_memories_block_when_memory_disabled() -> None:
    svc = _create_vault_agent_service()
    with patch("app.core.agents.agents.vault.get_settings") as mock_settings:
        settings_obj = MagicMock()
        settings_obj.memory_enabled = False
        mock_settings.return_value = settings_obj
        result = await svc._recall_memories_block("test")
    assert result == ""


# --- 9. _execute persists episode tagged vault_agent ---------------------


@pytest.mark.asyncio
async def test_execute_calls_persist_agent_episode_with_vault_tag() -> None:
    svc = _create_vault_agent_service()

    fake_result = MagicMock()
    fake_result.output = "vault output"
    fake_result.all_messages.return_value = []

    with patch(
        "app.core.agents.agents.vault.vault_agent.run",
        new=AsyncMock(return_value=fake_result),
    ):
        with patch("app.core.agents.agents.vault.persist_agent_episode") as mock_persist:
            await svc._execute(
                user_message="q",
                current_prompt="q",
                message_history=None,
                instructions=None,
                tier="standard",
                tier_model=None,
                static_cache=None,
            )

    mock_persist.assert_called_once()
    assert mock_persist.call_args.kwargs["agent_name"] == "vault_agent"


# --- 10. complex tier uses fallback path (no pipeline) --------------------


@pytest.mark.asyncio
async def test_execute_uses_fallback_path_for_complex_tier() -> None:
    svc = _create_vault_agent_service()

    fake_result = MagicMock()
    fake_result.output = "out"
    fake_result.all_messages.return_value = []

    with patch(
        "app.core.agents.agents.vault.vault_agent.run",
        new=AsyncMock(return_value=fake_result),
    ) as mock_run:
        with patch("app.core.agents.agents.vault.persist_agent_episode"):
            await svc._execute(
                user_message="q",
                current_prompt="q",
                message_history=None,
                instructions=None,
                tier="complex",
                tier_model=None,
                static_cache=None,
            )

    mock_run.assert_awaited_once()


# --- 11. chat wraps _execute exceptions -----------------------------------


@pytest.mark.asyncio
async def test_chat_wraps_execute_exceptions_as_agent_execution_error() -> None:
    svc = _create_vault_agent_service()

    async def _boom(**_kwargs: Any) -> None:
        raise RuntimeError("vault exploded")

    with patch.object(VaultAgent, "_execute", new=_boom):
        with patch("app.core.agents.agents.vault.get_settings", return_value=_settings_mock()):
            with pytest.raises(AgentExecutionError, match="Agent execution failed"):
                await svc.chat(_make_request("Hello"))


# --- 12. chat logs chat_started and chat_completed ------------------------


@pytest.mark.asyncio
async def test_chat_logs_chat_started_and_completed() -> None:
    svc = _create_vault_agent_service()

    with vault_agent.override(model=TestModel()):
        with patch("app.core.agents.agents.vault.get_settings", return_value=_settings_mock()):
            with patch("app.core.agents.base.logger") as mock_logger:
                await svc.chat(_make_request("Hello"))

    event_names = [call.args[0] for call in mock_logger.info.call_args_list if call.args]
    assert "agent.chat_started" in event_names
    assert "agent.chat_completed" in event_names


# --- 13. System prompt requires confirmation for destructive ops ---------


def test_system_prompt_requires_confirmation_for_destructive_ops() -> None:
    prompt_lower = VAULT_SYSTEM_PROMPT.lower()
    assert "confirm" in prompt_lower
    assert "dry_run" in prompt_lower
    assert "delete" in prompt_lower


# --- 14. System prompt describes frontmatter conventions -----------------


def test_system_prompt_describes_frontmatter_conventions() -> None:
    prompt_lower = VAULT_SYSTEM_PROMPT.lower()
    assert "frontmatter" in prompt_lower
    assert "title" in prompt_lower
    assert "tags" in prompt_lower


# --- 15. close() swallows RuntimeError on closed loop --------------------


@pytest.mark.asyncio
async def test_close_swallows_runtime_error_on_closed_loop() -> None:
    svc = _create_vault_agent_service()
    failing_client = AsyncMock()
    failing_client.aclose.side_effect = RuntimeError("closed")
    svc._deps.transit_http_client = failing_client
    svc._deps.obsidian_http_client = failing_client
    await svc.close()
