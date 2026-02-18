"""Tests for daily query quota tracker."""

from app.core.agents.quota import QueryQuotaTracker


def test_quota_allows_within_limit():
    tracker = QueryQuotaTracker(daily_limit=3)
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is True


def test_quota_rejects_over_limit():
    tracker = QueryQuotaTracker(daily_limit=2)
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is True
    assert tracker.check_and_increment("1.2.3.4") is False


def test_quota_tracks_per_ip():
    tracker = QueryQuotaTracker(daily_limit=1)
    assert tracker.check_and_increment("1.1.1.1") is True
    assert tracker.check_and_increment("2.2.2.2") is True
    assert tracker.check_and_increment("1.1.1.1") is False
    assert tracker.check_and_increment("2.2.2.2") is False


def test_quota_get_remaining():
    tracker = QueryQuotaTracker(daily_limit=5)
    assert tracker.get_remaining("1.2.3.4") == 5
    tracker.check_and_increment("1.2.3.4")
    assert tracker.get_remaining("1.2.3.4") == 4


def test_quota_get_remaining_at_zero():
    tracker = QueryQuotaTracker(daily_limit=1)
    tracker.check_and_increment("1.2.3.4")
    assert tracker.get_remaining("1.2.3.4") == 0
