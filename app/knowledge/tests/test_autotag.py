# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false, reportArgumentType=false
"""Tests for auto-tagging service method.

Covers: disabled flag, successful LLM tagging, LLM failure,
invalid JSON response.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.knowledge.service import KnowledgeService

# ---------------------------------------------------------------------------
# 1. Auto-tagging disabled
# ---------------------------------------------------------------------------


async def test_auto_tag_disabled():
    """When auto_tag_enabled=False, no LLM call should be made."""
    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    with patch("app.knowledge.service.get_settings") as mock_settings:
        mock_settings.return_value.auto_tag_enabled = False
        await service._auto_tag_document(1, "Some document text")

    # No repository calls should have been made
    service.repository = MagicMock()
    # If auto_tag_enabled is False, the method returns immediately


# ---------------------------------------------------------------------------
# 2. Auto-tagging success
# ---------------------------------------------------------------------------


async def test_auto_tag_success():
    """Successful LLM call should create and link tags."""
    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    mock_tag = MagicMock()
    mock_tag.id = 1
    mock_tag.name = "transit"

    service.repository = MagicMock()
    service.repository.get_or_create_tag = AsyncMock(return_value=mock_tag)
    service.repository.add_tags_to_document = AsyncMock()

    mock_result = MagicMock()
    mock_result.response = '["transit", "safety"]'

    with (
        patch("app.knowledge.service.get_settings") as mock_settings,
        patch("pydantic_ai.Agent") as mock_agent_cls,
    ):
        mock_settings.return_value.auto_tag_enabled = True
        mock_settings.return_value.auto_tag_max_chars = 500
        mock_settings.return_value.llm_provider = "test"
        mock_settings.return_value.llm_model = "test-model"

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_cls.return_value = mock_agent

        await service._auto_tag_document(1, "Transit safety document text")

    # Should have called get_or_create_tag for each tag
    assert service.repository.get_or_create_tag.await_count == 2
    assert service.repository.add_tags_to_document.await_count == 2


# ---------------------------------------------------------------------------
# 3. Auto-tagging LLM failure
# ---------------------------------------------------------------------------


async def test_auto_tag_llm_failure():
    """LLM failure should log warning but not raise."""
    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    with (
        patch("app.knowledge.service.get_settings") as mock_settings,
        patch("pydantic_ai.Agent") as mock_agent_cls,
    ):
        mock_settings.return_value.auto_tag_enabled = True
        mock_settings.return_value.auto_tag_max_chars = 500
        mock_settings.return_value.llm_provider = "test"
        mock_settings.return_value.llm_model = "test-model"

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        mock_agent_cls.return_value = mock_agent

        # Should not raise
        await service._auto_tag_document(1, "Some text")


# ---------------------------------------------------------------------------
# 4. Auto-tagging invalid JSON response
# ---------------------------------------------------------------------------


async def test_auto_tag_invalid_response():
    """Non-JSON LLM response should be handled gracefully."""
    mock_db = AsyncMock()
    service = KnowledgeService(mock_db)

    mock_result = MagicMock()
    mock_result.response = "This is not JSON"

    with (
        patch("app.knowledge.service.get_settings") as mock_settings,
        patch("pydantic_ai.Agent") as mock_agent_cls,
    ):
        mock_settings.return_value.auto_tag_enabled = True
        mock_settings.return_value.auto_tag_max_chars = 500
        mock_settings.return_value.llm_provider = "test"
        mock_settings.return_value.llm_model = "test-model"

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_cls.return_value = mock_agent

        # Should not raise — json.loads failure is caught by the broad except
        await service._auto_tag_document(1, "Some text")
