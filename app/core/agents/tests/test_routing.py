"""Tests for multi-tier model routing classification."""

from app.core.agents.routing import classify_prompt


class TestClassifyPromptFastTier:
    """Fast tier: simple lookups, status checks."""

    def test_short_prompt(self) -> None:
        assert classify_prompt("hello") == "fast"

    def test_delay_query_english(self) -> None:
        assert classify_prompt("Which routes are delayed?") == "fast"

    def test_delay_query_latvian(self) -> None:
        assert classify_prompt("Kuri marsruti kavējas?") == "fast"

    def test_delay_query_latvian_no_diacritics(self) -> None:
        assert classify_prompt("Kuri marsruti kavejas?") == "fast"

    def test_schedule_lookup(self) -> None:
        assert classify_prompt("Show schedule for route 22") == "fast"

    def test_next_bus_query(self) -> None:
        assert classify_prompt("Next bus at Brivibas iela stop") == "fast"

    def test_stop_query(self) -> None:
        assert classify_prompt("Where is the nearest stop?") == "fast"

    def test_count_query(self) -> None:
        assert classify_prompt("How many buses are active right now?") == "fast"

    def test_count_latvian(self) -> None:
        assert classify_prompt("Cik autobusu ir aktivi?") == "fast"

    def test_single_route_status(self) -> None:
        assert classify_prompt("Is route 3 on time?") == "fast"

    def test_driver_lookup(self) -> None:
        assert classify_prompt("Is driver Janis available tomorrow?") == "fast"

    def test_vehicle_status(self) -> None:
        assert classify_prompt("What is the status of vehicle 1042?") == "fast"

    def test_simple_entity_lookup(self) -> None:
        """Prompt with only fast keyword goes to fast tier."""
        assert classify_prompt("Where is the nearest stop to me?") == "fast"


class TestClassifyPromptComplexTier:
    """Complex tier: analysis, bulk operations, optimization."""

    def test_analyze_with_pattern(self) -> None:
        """Analyze + pattern = 2 complex matches -> complex."""
        assert classify_prompt("Analyze the delay patterns across this week") == "complex"

    def test_compare_performance(self) -> None:
        """Compare alone with no fast matches -> complex."""
        assert classify_prompt("Compare performance of morning and evening shifts") == "complex"

    def test_optimize_keyword(self) -> None:
        """Suggest + optimize in same pattern still = 1, but no fast match -> complex."""
        assert classify_prompt("Suggest how to optimize the morning timetable") == "complex"

    def test_all_routes_query(self) -> None:
        assert classify_prompt("Give me a report on all routes performance") == "complex"

    def test_bulk_operation(self) -> None:
        assert (
            classify_prompt("Move all notes from planning folder to archive in bulk") == "complex"
        )

    def test_report_summary(self) -> None:
        """Report + summary = 2 complex matches -> complex."""
        assert classify_prompt("Generate a summary report of operations this month") == "complex"

    def test_trend_analysis(self) -> None:
        """Trend alone with no fast keywords -> complex."""
        assert classify_prompt("What are the ridership trends for the past quarter?") == "complex"

    def test_planning_request(self) -> None:
        assert classify_prompt("Help me plan the holiday schedule reorganization") == "complex"

    def test_latvian_analysis(self) -> None:
        assert classify_prompt("Analize kavesanas tendences visos marsrutos") == "complex"

    def test_restructure_keyword(self) -> None:
        assert classify_prompt("Restructure the entire vault folder organization") == "complex"


class TestClassifyPromptStandardTier:
    """Standard tier: moderate complexity, mixed signals, default."""

    def test_moderate_query(self) -> None:
        """Route number (fast) in context question -> fast, but no complex -> fast."""
        assert classify_prompt("What happened yesterday afternoon in the depot?") == "standard"

    def test_knowledge_search(self) -> None:
        assert classify_prompt("Find the training policy document for new hires") == "standard"

    def test_vault_note_creation(self) -> None:
        assert (
            classify_prompt("Create a note about today's dispatch meeting decisions") == "standard"
        )

    def test_mixed_signals(self) -> None:
        """Fast keyword (delay) + complex keyword (report) -> standard."""
        result = classify_prompt("Show the delay report for today")
        assert result == "standard"

    def test_no_pattern_match(self) -> None:
        assert classify_prompt("Tell me about the history of Riga's transit system") == "standard"

    def test_ambiguous_query(self) -> None:
        assert classify_prompt("I need help with something") == "standard"
