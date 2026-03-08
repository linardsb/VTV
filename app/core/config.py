"""Application configuration using pydantic-settings.

This module provides centralized configuration management:
- Environment variable loading from .env file
- Type-safe settings with validation
- Cached settings instance with @lru_cache
- Settings for application, CORS, and future database configuration
"""

import json
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TransitFeedConfig(BaseModel):
    """Configuration for a single GTFS-RT transit feed."""

    feed_id: str
    operator_name: str
    rt_vehicle_positions_url: str
    rt_trip_updates_url: str
    static_url: str
    poll_interval_seconds: int = 10
    enabled: bool = True


class Settings(BaseSettings):
    """Application-wide configuration.

    All settings can be overridden via environment variables.
    Environment variables are case-insensitive.
    Settings are loaded from .env file if present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Don't fail if .env file doesn't exist
        extra="ignore",
    )

    # Application metadata
    app_name: str = "VTV"
    version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"

    # Database
    database_url: str

    # CORS settings
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8123"]

    # LLM Provider
    llm_provider: str = "test"
    llm_model: str = "test-model"
    llm_fallback_provider: str | None = None
    llm_fallback_model: str | None = None

    # LLM API keys
    anthropic_api_key: str | None = None

    # Google Gemini
    google_api_key: str | None = None

    # Groq
    groq_api_key: str | None = None

    # Ollama (local LLM)
    ollama_base_url: str = "http://localhost:11434/v1"

    # Transit GTFS-RT feeds (Rigas Satiksme public endpoints)
    gtfs_rt_vehicle_positions_url: str = "https://saraksti.rigassatiksme.lv/vehicle_positions.pb"
    gtfs_rt_trip_updates_url: str = "https://saraksti.rigassatiksme.lv/trip_updates.pb"
    gtfs_rt_alerts_url: str = "https://saraksti.rigassatiksme.lv/gtfs_realtime.pb"
    gtfs_static_url: str = "https://saraksti.rigassatiksme.lv/gtfs.zip"
    gtfs_rt_cache_ttl_seconds: int = 10
    gtfs_static_cache_ttl_hours: int = 24

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_vehicle_ttl_seconds: int = 120

    # Multi-feed GTFS-RT (replaces single-feed URLs)
    transit_feeds_json: str = "[]"
    poller_enabled: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def transit_feeds(self) -> list[TransitFeedConfig]:
        """Parse transit feeds from JSON config, falling back to legacy single-feed URLs."""
        feeds_raw: list[dict[str, Any]] = json.loads(self.transit_feeds_json)
        if feeds_raw:
            return [TransitFeedConfig(**f) for f in feeds_raw]
        # Backward compatibility: build from legacy single-feed settings
        return [
            TransitFeedConfig(
                feed_id="riga",
                operator_name="Rigas Satiksme",
                rt_vehicle_positions_url=self.gtfs_rt_vehicle_positions_url,
                rt_trip_updates_url=self.gtfs_rt_trip_updates_url,
                static_url=self.gtfs_static_url,
                poll_interval_seconds=self.gtfs_rt_cache_ttl_seconds,
            )
        ]

    # Obsidian Local REST API
    obsidian_api_key: str | None = None
    obsidian_vault_url: str = "https://127.0.0.1:27124"
    obsidian_verify_ssl: bool = (
        False  # Local REST API uses self-signed certs; True in production with proper cert
    )

    # JWT Authentication
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"  # noqa: S105  # MUST be overridden via env
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Demo credentials (only used when environment=development)
    demo_user_password: str = "admin"  # noqa: S105

    # Rate limiting (requests per minute per IP)
    rate_limit_chat: str = "10/minute"
    rate_limit_transit: str = "30/minute"
    rate_limit_health: str = "60/minute"
    rate_limit_default: str = "120/minute"

    # Poller leader election (multi-worker safe)
    poller_leader_lock_ttl: int = 60

    # WebSocket live streaming
    ws_enabled: bool = True
    ws_heartbeat_interval_seconds: int = 30
    ws_max_connections: int = 100

    # Database connection pool (tuned for multi-worker deployment)
    db_pool_size: int = 3
    db_pool_max_overflow: int = 5
    db_pool_recycle: int = 3600

    # Historical position storage (TimescaleDB)
    position_history_enabled: bool = True
    position_history_retention_days: int = 90
    position_history_compression_after_days: int = 7
    position_history_batch_size: int = 500

    # Query quota (daily per IP)
    agent_daily_quota: int = 50

    # Embedding provider (mirrors LLM provider pattern)
    embedding_provider: str = "jina"  # jina, openai, local
    embedding_model: str = "jina-embeddings-v3"
    embedding_dimension: int = 1024
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None  # Custom endpoint for local/Jina

    # Reranker
    reranker_provider: str = "local"  # local, none
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 10

    # GlitchTip error tracking (Sentry-compatible)
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1

    # Document storage
    document_storage_path: str = "data/documents"

    # Knowledge base
    knowledge_chunk_size: int = 512
    knowledge_chunk_overlap: int = 50
    knowledge_search_limit: int = 50  # Candidates before reranking

    # Auto-tagging (LLM classification on document upload)
    auto_tag_enabled: bool = False
    auto_tag_max_chars: int = 500

    # NeTEx/SIRI compliance exports
    netex_codespace: str = "VTV"
    netex_participant_ref: str = "VTV"

    # Alerts system
    alerts_enabled: bool = True
    alerts_check_interval_seconds: int = 60

    # Fleet management / Traccar GPS gateway
    traccar_enabled: bool = False
    traccar_base_url: str = "http://traccar:8082"
    traccar_webhook_token: str = "vtv-traccar-webhook"  # noqa: S105
    fleet_telemetry_source: str = "hardware"
    fleet_obd_fields: list[str] = [
        "speed",
        "rpm",
        "fuel_level",
        "coolant_temp",
        "odometer",
        "engine_load",
        "battery_voltage",
    ]

    @model_validator(mode="after")
    def _reject_default_secrets_in_production(self) -> "Settings":
        """Refuse to start with default JWT secret in non-development environments."""
        if self.environment != "development" and self.jwt_secret_key == "CHANGE-ME-IN-PRODUCTION":  # noqa: S105
            msg = (
                f"JWT_SECRET_KEY must be overridden in production (environment={self.environment})"
            )
            raise ValueError(msg)
        if self.traccar_enabled and self.traccar_webhook_token == "vtv-traccar-webhook":  # noqa: S105
            msg = "TRACCAR_WEBHOOK_TOKEN must be overridden when Traccar is enabled in production"
            raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    The @lru_cache decorator ensures settings are only loaded once
    and reused across the application lifecycle.

    Returns:
        The application settings instance.
    """
    return Settings()  # pyright: ignore[reportCallIssue]
