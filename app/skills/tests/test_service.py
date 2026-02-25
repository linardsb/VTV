# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for SkillService business logic."""

from unittest.mock import AsyncMock

import pytest

from app.shared.schemas import PaginationParams
from app.skills.exceptions import SkillNotFoundError, SkillValidationError
from app.skills.schemas import SkillCreate, SkillUpdate
from app.skills.service import SkillService
from app.skills.tests.conftest import make_skill


@pytest.fixture
def service() -> SkillService:
    mock_db = AsyncMock()
    svc = SkillService(mock_db)
    svc.repository = AsyncMock()
    return svc


async def test_get_skill_success(service):
    skill = make_skill(id=1, name="Test")
    service.repository.get = AsyncMock(return_value=skill)

    result = await service.get_skill(1)
    assert result.id == 1
    assert result.name == "Test"
    service.repository.get.assert_awaited_once_with(1)


async def test_get_skill_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(SkillNotFoundError, match="Skill 999 not found"):
        await service.get_skill(999)


async def test_list_skills_pagination(service):
    skill_items = [
        make_skill(id=1, name="Skill A"),
        make_skill(id=2, name="Skill B"),
    ]
    service.repository.find = AsyncMock(return_value=skill_items)
    service.repository.count = AsyncMock(return_value=2)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_skills(pagination)

    assert len(result.items) == 2
    assert result.total == 2
    assert result.page == 1


async def test_create_skill_success(service):
    data = SkillCreate(
        name="New Skill",
        description="A new skill",
        content="Skill content here",
        category="transit_ops",
    )
    created = make_skill(id=10, name="New Skill")
    service.repository.get_by_name = AsyncMock(return_value=None)
    service.repository.create = AsyncMock(return_value=created)

    result = await service.create_skill(data)
    assert result.id == 10
    assert result.name == "New Skill"


async def test_create_skill_duplicate_name(service):
    data = SkillCreate(
        name="Existing",
        description="Duplicate",
        content="Content",
    )
    service.repository.get_by_name = AsyncMock(return_value=make_skill(name="Existing"))

    with pytest.raises(SkillValidationError, match="already exists"):
        await service.create_skill(data)


async def test_update_skill_success(service):
    skill = make_skill(id=1, name="Old Name")
    updated = make_skill(id=1, name="New Name")
    data = SkillUpdate(name="New Name")

    service.repository.get = AsyncMock(return_value=skill)
    service.repository.get_by_name = AsyncMock(return_value=None)
    service.repository.update = AsyncMock(return_value=updated)

    result = await service.update_skill(1, data)
    assert result.name == "New Name"


async def test_update_skill_not_found(service):
    service.repository.get = AsyncMock(return_value=None)
    data = SkillUpdate(name="New Name")

    with pytest.raises(SkillNotFoundError, match="Skill 999 not found"):
        await service.update_skill(999, data)


async def test_delete_skill_success(service):
    skill = make_skill(id=1)
    service.repository.get = AsyncMock(return_value=skill)
    service.repository.delete = AsyncMock()

    await service.delete_skill(1)
    service.repository.delete.assert_awaited_once_with(skill)


async def test_delete_skill_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(SkillNotFoundError, match="Skill 999 not found"):
        await service.delete_skill(999)


async def test_get_active_skills_content_empty(service):
    service.repository.list_active = AsyncMock(return_value=[])

    result = await service.get_active_skills_content()
    assert result == ""


async def test_get_active_skills_content_with_skills(service):
    skills = [
        make_skill(id=1, name="Skill A", content="Content A", priority=90),
        make_skill(id=2, name="Skill B", content="Content B", priority=50),
    ]
    service.repository.list_active = AsyncMock(return_value=skills)

    result = await service.get_active_skills_content()
    assert "AGENT SKILLS" in result
    assert "## Skill A" in result
    assert "Content A" in result
    assert "## Skill B" in result
    assert "Content B" in result


async def test_get_active_skills_content_respects_budget(service):
    # Create skills that exceed the 8000 char budget
    large_content = "X" * 5000
    skills = [
        make_skill(id=1, name="Big Skill", content=large_content, priority=90),
        make_skill(id=2, name="Another Big", content=large_content, priority=50),
    ]
    service.repository.list_active = AsyncMock(return_value=skills)

    result = await service.get_active_skills_content()
    # First skill should be included, second should be dropped due to budget
    assert "## Big Skill" in result
    assert "## Another Big" not in result


async def test_seed_default_skills_empty_table(service):
    service.repository.count = AsyncMock(return_value=0)
    service.repository.create = AsyncMock(
        side_effect=lambda data, **_kw: make_skill(name=data.name)
    )

    result = await service.seed_default_skills()
    assert len(result) == 5
    assert service.repository.create.await_count == 5


async def test_seed_default_skills_already_populated(service):
    service.repository.count = AsyncMock(return_value=3)

    result = await service.seed_default_skills()
    assert len(result) == 0
    service.repository.create.assert_not_awaited()


def test_skill_update_rejects_empty_body():
    """PATCH with all-None fields should raise a validation error."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="At least one field must be provided"):
        SkillUpdate.model_validate({})


def test_skill_update_rejects_all_none_body():
    """PATCH with explicit None values should raise a validation error."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="At least one field must be provided"):
        SkillUpdate.model_validate(
            {"name": None, "description": None, "content": None, "category": None}
        )
