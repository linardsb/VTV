"""Unit tests for app/core/agents/validation.py extended QA checks (AI-5.2)."""

from __future__ import annotations

import time

import pytest

from app.core.agents import validation as validation_module
from app.core.agents.tools.transit.static_cache import (
    GTFSStaticCache,
    RouteInfo,
    StopInfo,
)
from app.core.agents.validation import (
    ToolReturnRecord,
    ValidationContext,
    validate_transit_response,
)


@pytest.fixture(autouse=True)
def _reset_stale_flag() -> None:
    """Ensure module-level stale flag is reset between tests."""
    validation_module.last_stale_data_timestamp = 0.0


def _make_static_cache() -> GTFSStaticCache:
    """Build a small in-memory GTFS cache fixture."""
    cache = GTFSStaticCache()
    cache.routes = {
        "bus_22": RouteInfo(
            route_id="bus_22",
            route_short_name="22",
            route_long_name="Centrs - Jugla",
            route_type=3,
        ),
        "bus_3": RouteInfo(
            route_id="bus_3",
            route_short_name="3",
            route_long_name="Imanta - Centrs",
            route_type=3,
        ),
    }
    cache.stops = {
        "s1": StopInfo(
            stop_id="s1",
            stop_name="Br\u012bv\u012bbas iela",
            stop_lat=56.95,
            stop_lon=24.10,
        ),
        "s2": StopInfo(
            stop_id="s2",
            stop_name="Stacijas laukums",
            stop_lat=56.94,
            stop_lon=24.12,
        ),
    }
    return cache


# --- Route existence ---


def test_route_existence_known_route_no_issue() -> None:
    ctx = ValidationContext(static_cache=_make_static_cache())
    result = validate_transit_response("Route 22 leaves at 14:00.", ctx)
    assert not any(i.check_name == "route_existence" for i in result.issues)


def test_route_existence_unknown_route_emits_error() -> None:
    ctx = ValidationContext(static_cache=_make_static_cache())
    result = validate_transit_response("Route 250 leaves at 14:00.", ctx)
    existence = [i for i in result.issues if i.check_name == "route_existence"]
    assert len(existence) == 1
    assert existence[0].severity == "error"
    assert "250" in existence[0].description


def test_route_existence_no_cache_skips_check() -> None:
    ctx = ValidationContext(static_cache=None)
    result = validate_transit_response("Route 250 leaves at 14:00.", ctx)
    assert not any(i.check_name == "route_existence" for i in result.issues)


# --- Stop existence ---


def test_stop_existence_known_stop_no_issue() -> None:
    ctx = ValidationContext(static_cache=_make_static_cache())
    result = validate_transit_response(
        "The bus departs pietura Br\u012bv\u012bbas iela at 14:00.",
        ctx,
    )
    assert not any(i.check_name == "stop_existence" for i in result.issues)


def test_stop_existence_unknown_stop_emits_warning() -> None:
    ctx = ValidationContext(static_cache=_make_static_cache())
    result = validate_transit_response(
        "Pietura Vecpils\u0113ta is the next stop.",
        ctx,
    )
    stop_issues = [i for i in result.issues if i.check_name == "stop_existence"]
    assert len(stop_issues) == 1
    assert stop_issues[0].severity == "warning"


# --- Time consistency ---


def test_time_consistency_valid_time_no_issue() -> None:
    result = validate_transit_response("Departs at 14:30.", None)
    assert not any(i.check_name == "time_consistency" for i in result.issues)


def test_time_consistency_impossible_minute_emits_error() -> None:
    result = validate_transit_response("Arrives at 14:75.", None)
    time_issues = [i for i in result.issues if i.check_name == "time_consistency"]
    assert len(time_issues) == 1
    assert time_issues[0].severity == "error"
    assert "minutes=75" in time_issues[0].description


def test_time_consistency_overflow_hour_emits_error() -> None:
    result = validate_transit_response("Departs at 25:30.", None)
    time_issues = [i for i in result.issues if i.check_name == "time_consistency"]
    assert len(time_issues) == 1
    assert "hours=25" in time_issues[0].description


# --- Citation grounding ---


def test_citation_grounding_valid_citation_no_issue() -> None:
    ctx = ValidationContext(
        tool_returns=[
            ToolReturnRecord(
                tool_name="search_knowledge",
                payload=[{"document_id": 42, "title": "Drivers handbook"}],
            )
        ],
    )
    result = validate_transit_response(
        "See [Drivers handbook](/lv/documents/42) for details.",
        ctx,
    )
    assert not any(i.check_name == "citation_grounding" for i in result.issues)


def test_citation_grounding_unground_citation_emits_error() -> None:
    ctx = ValidationContext(
        tool_returns=[
            ToolReturnRecord(
                tool_name="search_knowledge",
                payload=[{"document_id": 42, "title": "Drivers handbook"}],
            )
        ],
    )
    result = validate_transit_response(
        "See [fake doc](/lv/documents/99) for details.",
        ctx,
    )
    citation_issues = [i for i in result.issues if i.check_name == "citation_grounding"]
    assert len(citation_issues) == 1
    assert citation_issues[0].severity == "error"
    assert "99" in citation_issues[0].description


def test_citation_grounding_no_search_tool_skips_check() -> None:
    ctx = ValidationContext(
        tool_returns=[ToolReturnRecord(tool_name="query_bus_status", payload={"timestamp": 0})],
    )
    result = validate_transit_response(
        "See [some doc](/lv/documents/99) for details.",
        ctx,
    )
    assert not any(i.check_name == "citation_grounding" for i in result.issues)


def test_citation_grounding_dict_results_payload() -> None:
    ctx = ValidationContext(
        tool_returns=[
            ToolReturnRecord(
                tool_name="search_knowledge",
                payload={"results": [{"document_id": 7}]},
            )
        ],
    )
    result = validate_transit_response(
        "See [doc](/en/documents/7) and [bad](/en/documents/8).",
        ctx,
    )
    citation_issues = [i for i in result.issues if i.check_name == "citation_grounding"]
    assert len(citation_issues) == 1
    assert "8" in citation_issues[0].description


# --- Language match ---


def test_language_match_lv_to_lv_no_issue() -> None:
    ctx = ValidationContext(
        user_message="Kad pien\u0101k autobuss?",
    )
    result = validate_transit_response(
        "Mar\u0161ruts 22 pien\u0101k pl\u012bksten 08:00.",
        ctx,
    )
    assert not any(i.check_name == "language_match" for i in result.issues)


def test_language_match_lv_to_en_emits_error() -> None:
    ctx = ValidationContext(
        user_message="Kad pien\u0101k autobuss \u0161odien?",
    )
    result = validate_transit_response(
        "The bus route 22 arrives at 08:00 with the schedule.",
        ctx,
    )
    lang_issues = [i for i in result.issues if i.check_name == "language_match"]
    assert len(lang_issues) == 1
    assert lang_issues[0].severity == "error"


# --- Stale data per-response ---


def test_stale_data_per_response_old_timestamp_emits_warning() -> None:
    old_ts = time.time() - 600
    ctx = ValidationContext(
        tool_returns=[
            ToolReturnRecord(
                tool_name="query_bus_status",
                payload={"timestamp": old_ts, "buses": []},
            )
        ],
    )
    result = validate_transit_response("All buses on time.", ctx)
    stale_issues = [i for i in result.issues if i.check_name == "stale_data"]
    assert len(stale_issues) == 1
    assert stale_issues[0].severity == "warning"


def test_stale_data_per_response_fresh_timestamp_no_issue() -> None:
    fresh_ts = time.time() - 30
    ctx = ValidationContext(
        tool_returns=[
            ToolReturnRecord(
                tool_name="query_bus_status",
                payload={"timestamp": fresh_ts, "buses": []},
            )
        ],
    )
    result = validate_transit_response("All buses on time.", ctx)
    assert not any(i.check_name == "stale_data" for i in result.issues)


# --- Existing checks: severity verification ---


def test_existing_route_plausibility_now_returns_error_severity() -> None:
    result = validate_transit_response("Route 1500 status.", None)
    plausibility = [i for i in result.issues if i.check_name == "route_plausibility"]
    assert len(plausibility) == 1
    assert plausibility[0].severity == "error"


# --- Result wiring ---


def test_validation_result_is_valid_false_when_any_issue() -> None:
    result = validate_transit_response("Route 1500 fails.", None)
    assert result.is_valid is False
    assert len(result.issues) >= 1


def test_validation_result_is_valid_true_when_no_issues() -> None:
    result = validate_transit_response("Route 22 is on time at 08:00.", None)
    assert result.is_valid is True
    assert result.issues == []


def test_warnings_field_mirrors_issue_descriptions() -> None:
    result = validate_transit_response("Route 1500 at 25:30.", None)
    assert result.warnings == [i.description for i in result.issues]
