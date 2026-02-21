"""Tests for app.core.config module."""

import json
import os
from unittest.mock import patch

from app.core.config import Settings, TransitFeedConfig, get_settings


def create_settings() -> Settings:
    """Create Settings instance for testing.

    Helper function for creating Settings in tests. pydantic-settings loads
    required fields from environment variables at runtime. Mypy's static analysis
    doesn't understand this and expects constructor arguments. This is a known
    limitation with pydantic-settings, so we suppress the call-arg error.

    Returns:
        Settings instance loaded from environment variables.
    """
    return Settings()  # pyright: ignore[reportCallIssue]


def test_settings_defaults() -> None:
    """Test Settings instantiation with default values."""
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
            "LOG_LEVEL": "INFO",  # Override .env file to test default value
        },
    ):
        settings = create_settings()

        assert settings.app_name == "VTV"
        assert settings.version == "0.1.0"
        assert settings.environment == "development"
        assert settings.log_level == "INFO"
        assert settings.api_prefix == "/api"
        assert "http://localhost:3000" in settings.allowed_origins
        assert "http://localhost:8123" in settings.allowed_origins


def test_settings_from_environment() -> None:
    """Test Settings can be overridden by environment variables."""
    with patch.dict(
        os.environ,
        {
            "APP_NAME": "Test App",
            "VERSION": "1.0.0",
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
            "API_PREFIX": "/v1",
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        },
    ):
        settings = create_settings()

        assert settings.app_name == "Test App"
        assert settings.version == "1.0.0"
        assert settings.environment == "production"
        assert settings.log_level == "DEBUG"
        assert settings.api_prefix == "/v1"


def test_allowed_origins_parsing() -> None:
    """Test allowed_origins parsing from environment variable.

    Note: pydantic-settings expects JSON array format for list fields.
    """
    with patch.dict(
        os.environ,
        {
            "ALLOWED_ORIGINS": '["http://example.com","http://localhost:3000","http://test.com"]',
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        },
    ):
        settings = create_settings()

        assert len(settings.allowed_origins) == 3
        assert "http://example.com" in settings.allowed_origins
        assert "http://localhost:3000" in settings.allowed_origins
        assert "http://test.com" in settings.allowed_origins


def test_get_settings_caching() -> None:
    """Test get_settings() returns cached instance."""
    # Clear the cache first
    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    # Should return the same instance (cached)
    assert settings1 is settings2


def test_settings_case_insensitive() -> None:
    """Test settings are case-insensitive."""
    with patch.dict(
        os.environ,
        {
            "app_name": "Lower Case App",
            "ENVIRONMENT": "PRODUCTION",
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        },
    ):
        settings = create_settings()

        assert settings.app_name == "Lower Case App"
        assert settings.environment == "PRODUCTION"


def test_transit_feeds_from_json() -> None:
    """Test transit_feeds computed property parses TRANSIT_FEEDS_JSON."""
    feeds_json = json.dumps(
        [
            {
                "feed_id": "riga",
                "operator_name": "Rigas Satiksme",
                "rt_vehicle_positions_url": "https://example.com/vp",
                "rt_trip_updates_url": "https://example.com/tu",
                "static_url": "https://example.com/static.zip",
                "poll_interval_seconds": 15,
                "enabled": False,
            },
            {
                "feed_id": "jurmala",
                "operator_name": "Jurmala Transit",
                "rt_vehicle_positions_url": "https://example.com/j/vp",
                "rt_trip_updates_url": "https://example.com/j/tu",
                "static_url": "https://example.com/j/static.zip",
            },
        ]
    )
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
            "TRANSIT_FEEDS_JSON": feeds_json,
        },
    ):
        settings = create_settings()

        assert len(settings.transit_feeds) == 2
        assert settings.transit_feeds[0].feed_id == "riga"
        assert settings.transit_feeds[0].operator_name == "Rigas Satiksme"
        assert settings.transit_feeds[0].poll_interval_seconds == 15
        assert settings.transit_feeds[0].enabled is False
        assert settings.transit_feeds[1].feed_id == "jurmala"
        assert settings.transit_feeds[1].poll_interval_seconds == 10
        assert settings.transit_feeds[1].enabled is True


def test_transit_feeds_legacy_fallback() -> None:
    """Test transit_feeds falls back to legacy single-feed URLs when JSON is empty."""
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
            "TRANSIT_FEEDS_JSON": "[]",
            "GTFS_RT_VEHICLE_POSITIONS_URL": "https://legacy.com/vp",
            "GTFS_RT_TRIP_UPDATES_URL": "https://legacy.com/tu",
            "GTFS_STATIC_URL": "https://legacy.com/static.zip",
        },
    ):
        settings = create_settings()

        assert len(settings.transit_feeds) == 1
        assert settings.transit_feeds[0].feed_id == "riga"
        assert settings.transit_feeds[0].operator_name == "Rigas Satiksme"
        assert settings.transit_feeds[0].rt_vehicle_positions_url == "https://legacy.com/vp"
        assert settings.transit_feeds[0].rt_trip_updates_url == "https://legacy.com/tu"
        assert settings.transit_feeds[0].static_url == "https://legacy.com/static.zip"


def test_transit_feed_config_defaults() -> None:
    """Test TransitFeedConfig defaults for poll_interval and enabled."""
    config = TransitFeedConfig(
        feed_id="test",
        operator_name="Test Operator",
        rt_vehicle_positions_url="https://example.com/vp",
        rt_trip_updates_url="https://example.com/tu",
        static_url="https://example.com/static.zip",
    )

    assert config.poll_interval_seconds == 10
    assert config.enabled is True
