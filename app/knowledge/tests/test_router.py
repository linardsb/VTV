"""Tests for RAG query router."""

from unittest.mock import patch

from app.knowledge.router import RoutingDecision, needs_rag


class TestNeedsRagTransitQueries:
    """Transit/schedule queries should skip RAG."""

    def test_latvian_route_delay(self) -> None:
        result = needs_rag("Kuri marsruti kavejas?")
        assert result.needs_rag is False
        assert result.skip_score > 0

    def test_english_route_delay(self) -> None:
        result = needs_rag("Which routes are delayed?")
        assert result.needs_rag is False

    def test_next_bus_at_stop(self) -> None:
        result = needs_rag("Next bus at Brivibas iela stop")
        assert result.needs_rag is False

    def test_route_on_time(self) -> None:
        result = needs_rag("Is route 3 on time?")
        assert result.needs_rag is False

    def test_active_buses_english(self) -> None:
        result = needs_rag("How many buses are active right now?")
        assert result.needs_rag is False

    def test_active_buses_latvian(self) -> None:
        result = needs_rag("Cik autobusu ir aktivi?")
        assert result.needs_rag is False

    def test_schedule_lookup(self) -> None:
        result = needs_rag("Show me the schedule for route 22")
        assert result.needs_rag is False

    def test_stop_search(self) -> None:
        result = needs_rag("Find the nearest stop to me")
        assert result.needs_rag is False

    def test_tram_status(self) -> None:
        result = needs_rag("Is the tram currently running?")
        assert result.needs_rag is False

    def test_driver_lookup(self) -> None:
        result = needs_rag("Which driver is on vehicle 42?")
        assert result.needs_rag is False


class TestNeedsRagKnowledgeQueries:
    """Knowledge/policy/SOP queries should use RAG."""

    def test_latvian_procedure_query(self) -> None:
        result = needs_rag("Kada ir procedura par virsstundam?")
        assert result.needs_rag is True
        assert result.rag_score > 0

    def test_english_policy_query(self) -> None:
        result = needs_rag("What is the overtime policy?")
        assert result.needs_rag is True

    def test_find_safety_guidelines(self) -> None:
        result = needs_rag("Find driver safety guidelines")
        assert result.needs_rag is True

    def test_compliance_manual_query(self) -> None:
        result = needs_rag("What does the compliance manual say about inspections?")
        assert result.needs_rag is True

    def test_latvian_how_to(self) -> None:
        result = needs_rag("Ka rikoties, ja ir avarija?")
        assert result.needs_rag is True

    def test_training_sop(self) -> None:
        result = needs_rag("Show me the training SOP")
        assert result.needs_rag is True

    def test_document_search(self) -> None:
        result = needs_rag("Find document about regulations")
        assert result.needs_rag is True

    def test_handbook_query(self) -> None:
        result = needs_rag("Where is the employee handbook?")
        assert result.needs_rag is True

    def test_audit_procedure(self) -> None:
        result = needs_rag("What is the audit procedure?")
        assert result.needs_rag is True

    def test_how_to_procedural(self) -> None:
        result = needs_rag("How to report an incident")
        assert result.needs_rag is True


class TestNeedsRagMixedQueries:
    """Ambiguous queries - test tie-breaking behavior."""

    def test_mixed_signals_route_safety(self) -> None:
        """Route safety has both transit and knowledge signals."""
        result = needs_rag("Tell me about route 3 safety procedures")
        # Both signals present - result depends on signal counts
        assert isinstance(result.needs_rag, bool)
        assert result.rag_score > 0
        assert result.skip_score > 0

    def test_short_generic_query_skips(self) -> None:
        """Short generic queries with no RAG signals should skip."""
        result = needs_rag("Hello")
        assert result.needs_rag is False
        assert result.rag_score == 0

    def test_empty_query_skips(self) -> None:
        result = needs_rag("")
        assert result.needs_rag is False
        assert result.rag_score == 0
        assert result.skip_score == 0

    def test_tie_goes_to_skip(self) -> None:
        """When rag_score == skip_score, needs_rag should be False."""
        result = needs_rag("safety on the bus")
        # safety = RAG signal, bus = skip signal => tie => skip
        assert result.needs_rag is False


class TestNeedsRagReturnType:
    """Verify RoutingDecision structure."""

    def test_returns_named_tuple(self) -> None:
        result = needs_rag("test query")
        assert isinstance(result, RoutingDecision)
        assert isinstance(result.needs_rag, bool)
        assert isinstance(result.rag_score, int)
        assert isinstance(result.skip_score, int)


class TestNeedsRagLogging:
    """Verify structured logging of routing decisions."""

    def test_logs_decision_with_hash(self) -> None:
        with patch("app.knowledge.router.logger") as mock_logger:
            needs_rag("What is the overtime policy?")
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "knowledge.router.decision"
            assert "query_hash" in call_args[1]
            assert "needs_rag" in call_args[1]
            assert "rag_score" in call_args[1]
            assert "skip_score" in call_args[1]

    def test_query_hash_is_deterministic(self) -> None:
        with patch("app.knowledge.router.logger") as mock_logger:
            needs_rag("test query")
            hash1 = mock_logger.info.call_args[1]["query_hash"]

        with patch("app.knowledge.router.logger") as mock_logger:
            needs_rag("test query")
            hash2 = mock_logger.info.call_args[1]["query_hash"]

        assert hash1 == hash2

    def test_different_queries_different_hashes(self) -> None:
        with patch("app.knowledge.router.logger") as mock_logger:
            needs_rag("query one")
            hash1 = mock_logger.info.call_args[1]["query_hash"]

        with patch("app.knowledge.router.logger") as mock_logger:
            needs_rag("query two")
            hash2 = mock_logger.info.call_args[1]["query_hash"]

        assert hash1 != hash2
