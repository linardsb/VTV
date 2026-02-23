# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for EventService business logic."""

import datetime
from unittest.mock import AsyncMock

import pytest

from app.events.exceptions import EventNotFoundError
from app.events.schemas import EventCreate, EventUpdate
from app.events.service import EventService
from app.events.tests.conftest import make_event
from app.shared.models import utcnow
from app.shared.schemas import PaginationParams


@pytest.fixture
def service() -> EventService:
    mock_db = AsyncMock()
    svc = EventService(mock_db)
    svc.repository = AsyncMock()
    return svc


async def test_get_event_success(service):
    event = make_event(id=1, title="Inspection")
    service.repository.get = AsyncMock(return_value=event)

    result = await service.get_event(1)
    assert result.id == 1
    assert result.title == "Inspection"
    service.repository.get.assert_awaited_once_with(1)


async def test_get_event_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(EventNotFoundError, match="Event 999 not found"):
        await service.get_event(999)


async def test_list_events(service):
    events = [
        make_event(id=1, title="Inspection"),
        make_event(id=2, title="Detour"),
    ]
    service.repository.list = AsyncMock(return_value=events)
    service.repository.count = AsyncMock(return_value=2)

    pagination = PaginationParams(page=1, page_size=20)
    result = await service.list_events(pagination)

    assert len(result.items) == 2
    assert result.total == 2
    assert result.page == 1


async def test_list_events_with_date_filter(service):
    now = utcnow()
    events = [make_event(id=1)]
    service.repository.list = AsyncMock(return_value=events)
    service.repository.count = AsyncMock(return_value=1)

    pagination = PaginationParams(page=1, page_size=20)
    start = now - datetime.timedelta(days=7)
    end = now + datetime.timedelta(days=7)
    result = await service.list_events(pagination, start_date=start, end_date=end)

    assert len(result.items) == 1
    service.repository.list.assert_awaited_once()


async def test_create_event_success(service):
    now = utcnow()
    data = EventCreate(
        title="New Event",
        start_datetime=now,
        end_datetime=now + datetime.timedelta(hours=2),
        priority="medium",
        category="maintenance",
    )
    created = make_event(id=10, title="New Event")
    service.repository.create = AsyncMock(return_value=created)

    result = await service.create_event(data)
    assert result.id == 10
    assert result.title == "New Event"


async def test_update_event_success(service):
    event = make_event(id=1, title="Old Title")
    updated = make_event(id=1, title="New Title")
    data = EventUpdate(title="New Title")

    service.repository.get = AsyncMock(return_value=event)
    service.repository.update = AsyncMock(return_value=updated)

    result = await service.update_event(1, data)
    assert result.title == "New Title"


async def test_update_event_not_found(service):
    service.repository.get = AsyncMock(return_value=None)
    data = EventUpdate(title="New Title")

    with pytest.raises(EventNotFoundError, match="Event 999 not found"):
        await service.update_event(999, data)


async def test_delete_event_success(service):
    event = make_event(id=1)
    service.repository.get = AsyncMock(return_value=event)
    service.repository.delete = AsyncMock()

    await service.delete_event(1)
    service.repository.delete.assert_awaited_once_with(event)


async def test_delete_event_not_found(service):
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(EventNotFoundError, match="Event 999 not found"):
        await service.delete_event(999)


def test_event_update_rejects_empty_body():
    """PATCH with all-None fields should raise a validation error."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="At least one field must be provided"):
        EventUpdate.model_validate({})


def test_event_update_rejects_all_none_body():
    """PATCH with explicit None values should raise a validation error."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="At least one field must be provided"):
        EventUpdate.model_validate(
            {"title": None, "description": None, "priority": None, "category": None}
        )


def test_event_create_rejects_invalid_priority():
    """Create with invalid priority should raise validation error."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EventCreate(
            title="Test",
            start_datetime=utcnow(),
            end_datetime=utcnow(),
            priority="critical",  # intentionally invalid
        )
