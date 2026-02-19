"""Application configuration using pydantic-settings.

This module provides centralized configuration management:
- Environment variable loading from .env file
- Type-safe settings with validation
- Cached settings instance with @lru_cache
- Settings for application, CORS, and future database configuration
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Ollama (local LLM)
    ollama_base_url: str = "http://localhost:11434/v1"

    # Transit GTFS-RT feeds (Rigas Satiksme public endpoints)
    gtfs_rt_vehicle_positions_url: str = "https://saraksti.rigassatiksme.lv/vehicle_positions.pb"
    gtfs_rt_trip_updates_url: str = "https://saraksti.rigassatiksme.lv/trip_updates.pb"
    gtfs_rt_alerts_url: str = "https://saraksti.rigassatiksme.lv/gtfs_realtime.pb"
    gtfs_static_url: str = "https://saraksti.rigassatiksme.lv/gtfs.zip"
    gtfs_rt_cache_ttl_seconds: int = 10
    gtfs_static_cache_ttl_hours: int = 24

    # Obsidian Local REST API
    obsidian_api_key: str | None = None
    obsidian_vault_url: str = "https://127.0.0.1:27124"

    # Rate limiting (requests per minute per IP)
    rate_limit_chat: str = "10/minute"
    rate_limit_transit: str = "30/minute"
    rate_limit_health: str = "60/minute"
    rate_limit_default: str = "120/minute"

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

    # Document storage
    document_storage_path: str = "data/documents"

    # Knowledge base
    knowledge_chunk_size: int = 512
    knowledge_chunk_overlap: int = 50
    knowledge_search_limit: int = 50  # Candidates before reranking


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    The @lru_cache decorator ensures settings are only loaded once
    and reused across the application lifecycle.

    Returns:
        The application settings instance.
    """
    return Settings()  # pyright: ignore[reportCallIssue]
