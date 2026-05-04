"""Application configuration using pydantic-settings.

This module provides centralized configuration management:
- Environment variable loading from .env file
- Type-safe settings with validation
- Cached settings instance with @lru_cache
- Settings for application, CORS, and future database configuration
"""

import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

FeedType = Literal["gtfs_rt", "scraper", "gps_text"]


class TransitFeedConfig(BaseModel):
    """Configuration for a single transit feed.

    Supports three feed types:
    - gtfs_rt: Standard GTFS-Realtime protobuf feeds
    - scraper: JSON API scraper (e.g. Daugavpils)
    - gps_text: Semicolon-delimited GPS text (e.g. marsruti.lv)
    """

    feed_id: str
    operator_name: str
    rt_vehicle_positions_url: str
    rt_trip_updates_url: str = ""
    static_url: str = ""
    poll_interval_seconds: int = 10
    enabled: bool = True
    feed_type: FeedType = "gtfs_rt"


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

    # Multi-tier model routing (optional — falls back to primary model when None)
    llm_fast_provider: str | None = None
    llm_fast_model: str | None = None
    llm_standard_provider: str | None = None
    llm_standard_model: str | None = None
    llm_complex_provider: str | None = None
    llm_complex_model: str | None = None

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

    # Daily GTFS static auto-import (LV-1.2)
    gtfs_auto_import_enabled: bool = False
    gtfs_auto_import_hour_utc: int = 3

    # Adaptive polling (LV-2.3)
    transit_adaptive_polling_enabled: bool = True
    transit_peak_hours: str = "6-9,16-19"
    transit_night_hours: str = "23-5"

    # Train WebSocket listener (LV-2.2)
    train_ws_enabled: bool = True
    train_ws_url: str = "wss://trainmap.pv.lv/ws"
    train_ws_reconnect_max_seconds: int = 60

    # OwnTracks MQTT listener (LV-3.1)
    owntracks_mqtt_enabled: bool = False
    owntracks_mqtt_broker_url: str = "mqtt://localhost:1883"
    owntracks_mqtt_username: str | None = None
    owntracks_mqtt_password: str | None = None
    owntracks_mqtt_topic_filter: str = "owntracks/+/+"
    owntracks_mqtt_reconnect_max_seconds: int = 60

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

    # Per-user rate limit tiers (OPS-4.1)
    rate_limit_tier_admin: str = "1000/minute"
    rate_limit_tier_dispatcher: str = "300/minute"
    rate_limit_tier_editor: str = "100/minute"
    rate_limit_tier_viewer: str = "50/minute"
    rate_limit_tier_anonymous: str = "30/minute"
    rate_limit_agent_chat: str = "10/minute"
    rate_limit_analytics_export: str = "5/hour"

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

    # E-ticket validation data pipeline (ML-1.2)
    eticket_archive_base_url: str = "https://data.rigassatiksme.lv/eticket/"
    eticket_batch_size: int = 5000
    eticket_compression_after_days: int = 30
    eticket_retention_years: int = 5
    eticket_max_archive_size_mb: int = 500  # ZIP bomb guard

    # Query quota (daily per IP)
    agent_daily_quota: int = 50

    # Embedding provider (mirrors LLM provider pattern)
    embedding_provider: str = "jina"  # jina, openai, local
    embedding_model: str = "jina-embeddings-v3"
    embedding_dimension: int = 1024
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None  # Custom endpoint for local/Jina

    # Embedding cache (Redis-backed, avoids redundant API calls)
    embedding_cache_enabled: bool = True
    embedding_cache_ttl: int = 3600  # seconds (1 hour)

    # Reranker
    reranker_provider: str = "local"  # local, none
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 10

    # Latvian UDPipe lemmatizer (KB-2) — default OFF so the model file is opt-in.
    # Enable only after running `make download-udpipe-model`.
    latvian_lemmatizer_enabled: bool = False
    udpipe_model_path: str = "models/latvian-ud-2.5.udpipe"

    # Confidence threshold (filter reranked results below this score)
    knowledge_confidence_threshold: float = 0.3

    # GlitchTip error tracking (Sentry-compatible)
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1

    # Document storage
    document_storage_path: str = "data/documents"

    # Knowledge base
    knowledge_chunk_size: int = 512
    knowledge_chunk_overlap: int = 100
    knowledge_search_limit: int = 50  # Candidates before reranking

    # Temporal boost (recent documents score higher in search)
    temporal_boost_enabled: bool = True
    temporal_boost_today: float = 1.5
    temporal_boost_this_week: float = 1.2
    temporal_boost_this_month: float = 1.0
    temporal_boost_older: float = 0.8

    # RRF weight tuning (query-type-adaptive)
    rrf_keyword_vector_weight: float = 0.3
    rrf_keyword_text_weight: float = 0.7
    rrf_semantic_vector_weight: float = 0.7
    rrf_semantic_text_weight: float = 0.3
    rrf_mixed_vector_weight: float = 0.5
    rrf_mixed_text_weight: float = 0.5

    # KB-4: search feedback loop — tuned RRF weights from thumbs-up/down.
    knowledge_feedback_enabled: bool = False
    knowledge_rrf_recompute_cron_hour: int = Field(default=3, ge=0, le=23)
    knowledge_rrf_feedback_window_days: int = Field(default=30, ge=1, le=365)
    knowledge_rrf_min_signals_per_type: int = Field(default=20, ge=1)
    knowledge_rrf_blend_weight: float = Field(default=0.5, ge=0.0, le=1.0)

    # LV-3.3: OpenTripPlanner multi-modal journey planner proxy.
    otp_enabled: bool = False
    otp_base_url: str = "http://otp:8080"
    otp_router_id: str = "default"
    otp_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    otp_cache_ttl_seconds: int = Field(default=300, ge=0, le=3600)
    otp_max_itineraries: int = Field(default=5, ge=1, le=10)
    otp_max_walk_distance_m: int = Field(default=2000, ge=0, le=10000)

    # LV-3.4: Trip share links (signed tokens, short-lived Redis state).
    share_link_secret_key: str | None = None
    share_link_default_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    share_link_max_ttl_seconds: int = Field(default=86400, ge=60, le=604800)

    # KB-5: Entity/knowledge-graph overlay. Extracts named entities (routes,
    # stops, regulations, optionally people/orgs via spaCy) during ingest and
    # boosts RRF scores for chunks that share entities with the query.
    entity_extraction_enabled: bool = True
    entity_boost_enabled: bool = True
    entity_boost_multiplier: float = Field(default=1.3, ge=1.0, le=3.0)
    entity_mention_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    entity_extractor_provider: Literal["regex", "spacy"] = "regex"

    # RAG query router (skip knowledge search for transit/schedule queries)
    knowledge_router_enabled: bool = True

    # Auto-tagging (LLM classification on document upload)
    auto_tag_enabled: bool = False
    auto_tag_max_chars: int = 500

    # HyDE query expansion (generate hypothetical answer before embedding)
    knowledge_hyde_enabled: bool = False
    knowledge_hyde_model: str | None = None  # None = use llm_fast or primary model
    knowledge_hyde_max_tokens: int = 200

    # Semantic chunking (heading-aware, replaces fixed-size for structured docs)
    knowledge_semantic_chunking_enabled: bool = True
    knowledge_chunk_target_size: int = 800
    knowledge_chunk_min_size: int = 256
    knowledge_chunk_max_size: int = 1500

    # Parent-child retrieval (attach parent section as context for matched child chunks)
    knowledge_parent_context_enabled: bool = True
    knowledge_parent_context_max_chars: int = 3000

    # NeTEx/SIRI compliance exports
    netex_codespace: str = "VTV"
    netex_participant_ref: str = "VTV"

    # Alerts system
    alerts_enabled: bool = True
    alerts_check_interval_seconds: int = 60

    # ML-3.3: Crowding prediction alerts
    alerts_crowding_enabled: bool = True
    alerts_crowding_check_interval_seconds: int = 120  # 2 min cycle
    alerts_crowding_dedup_minutes: int = 30

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

    # Geofence evaluator
    geofence_evaluator_enabled: bool = True
    geofence_check_interval_seconds: int = 30

    # ML anomaly detection (ML-4.2)
    ml_anomaly_evaluator_enabled: bool = True
    ml_anomaly_check_interval_seconds: int = 60
    ml_stuck_distance_threshold_m: float = 20.0
    ml_stuck_time_window_minutes: int = 10
    ml_gps_gap_threshold_minutes: int = 5
    ml_gps_gap_feed_outage_pct: int = 50
    ml_anomaly_cooldown_seconds: int = 900

    # ML load correlation (ML-3.1)
    ml_load_time_window_seconds: int = 60
    ml_load_distance_threshold_m: float = 100.0
    ml_load_min_correlation_pct: float = 80.0

    # Anomaly alert routing (ML-4.3)
    anomaly_recent_window_hours: int = 24
    anomaly_cooldown_critical_seconds: int = 1800
    anomaly_cooldown_warning_seconds: int = 900

    # ML-5.2: Daily adherence report
    analytics_adherence_enabled: bool = True
    analytics_adherence_threshold_pct: float = 85.0
    analytics_adherence_cron_hour: int = 6  # 06:00 UTC
    analytics_adherence_slack_webhook: str | None = None
    analytics_adherence_smtp_enabled: bool = False
    analytics_adherence_smtp_host: str = "localhost"
    analytics_adherence_smtp_port: int = 587
    analytics_adherence_smtp_from: str = "vtv@example.com"
    analytics_adherence_smtp_to: str = ""  # comma-separated

    # ETA Inference (ML-2.3)
    eta_service_enabled: bool = True
    eta_model_reload_interval_seconds: int = 300  # 5 min hot-reload check
    eta_fallback_enabled: bool = True

    # Off-route anomaly detection (ML-4.1)
    anomaly_offroute_enabled: bool = True
    anomaly_offroute_check_interval_seconds: int = 60
    anomaly_offroute_buffer_meters: int = 50
    anomaly_offroute_consecutive_hits: int = 3

    # Memory lifecycle
    memory_enabled: bool = True
    memory_procedural_decay_days: int = 90
    memory_episodic_decay_days: int = 30
    memory_query_pattern_decay_days: int = 60
    memory_promotion_threshold: int = 3
    memory_max_recall_results: int = 5
    memory_duplicate_threshold: float = 0.95
    memory_merge_threshold: float = 0.92
    memory_decay_min_weight: float = 0.1

    # Memory agent integration (AI-3.4)
    memory_recall_min_score: float = 0.3
    memory_context_injection_limit: int = 10
    memory_llm_merge_enabled: bool = False
    memory_compaction_cron_hour: int = 3
    memory_promotion_cron_hour: int = 3

    # Durable job queue (OPS-3.2)
    background_queue_enabled: bool = False
    arq_max_jobs: int = 10
    arq_job_timeout_seconds: int = 3600
    arq_retry_count: int = 3
    arq_compaction_interval_hours: int = 6
    arq_promotion_cron_hour: int = 3

    # Self-correction loop (AI-5.1)
    agent_self_correction_enabled: bool = True
    agent_max_correction_rounds: int = 1  # Transit needs fast responses; 1 retry only

    # Multi-agent auto-routing (AI-6.3)
    agent_multi_agent_enabled: bool = False

    # AI-6.4 Progressive L3 skills
    agent_progressive_skills_enabled: bool = True

    # AI-6.5 Confidence-based re-routing
    agent_confidence_reroute_enabled: bool = True
    agent_confidence_reroute_threshold: float = 0.3

    # AI-7.3/7.4 Eval framework
    eval_judge_enabled: bool = True
    eval_baseline_tolerance_pct: float = 3.0

    # Prompt injection detection (AI-9.1) + blocking (AI-9.2)
    prompt_injection_mode: Literal["warn", "block"] = "warn"
    prompt_injection_block_threshold: float = 0.85
    prompt_injection_warn_threshold: float = 0.5

    # Output-side data exfiltration validation (AI-9.3)
    output_validation_enabled: bool = True
    output_validation_mode: Literal["warn", "block"] = "warn"
    output_validation_block_threshold: float = 0.80

    # Circuit breaker (AI-8.1) — LLM provider fast-fail
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_s: float = 30.0
    circuit_breaker_success_threshold: int = 2
    circuit_breaker_failure_rate_threshold: float = 0.5

    # Weather ETL (ML-1.3)
    weather_etl_enabled: bool = False
    weather_station_url: str = ""
    weather_observations_url: str = ""
    weather_phenomena_url: str = ""
    weather_etl_interval_seconds: int = 3600
    weather_etl_leader_lock_ttl: int = 120
    weather_history_retention_days: int = 365

    # Traffic ETL (ML-1.3)
    traffic_etl_enabled: bool = False
    traffic_counts_url: str = ""
    traffic_accidents_url: str = ""
    traffic_etl_cron_hour: int = 4

    # Historical GTFS archive (data.gov.lv)
    data_gov_lv_base_url: str = "https://data.gov.lv/dati/api/3"
    data_gov_lv_dataset_id: str = "rigas-satiksmes-marsrutu-saraksti-gtfs"
    gtfs_backfill_rate_limit_seconds: float = 1.0

    # CKAN Datastore SQL API (LV-1.1 — intercity transit data)
    # NOTE (T-003): default disabled. The agent tools `search_intercity_*`
    # query data.gov.lv assuming each GTFS table is published as a separate
    # Datastore-enabled resource, but the actual ATD dataset (`atd-gtfs`)
    # publishes a single GTFS ZIP. The placeholder resource IDs in
    # ``app/transit/ckan_client.py:CKAN_RESOURCES`` will not resolve until
    # the data ingestion path is redesigned to import the ZIP into local
    # tables. Keep this flag off in production until that work lands.
    intercity_search_enabled: bool = False
    ckan_datastore_sql_url: str = "https://data.gov.lv/dati/api/3/action/datastore_search_sql"
    ckan_cache_ttl_s: int = 300
    ckan_rate_limit_delay_s: float = 1.0

    # Public Developer API (ML-5.3)
    public_api_enabled: bool = True
    public_api_default_rate_limit: int = 60  # requests per minute per key
    public_api_tier_limits: dict[str, int] = {
        "free": 60,
        "basic": 300,
        "pro": 1000,
    }
    public_api_key_prefix: str = "vtv_pk_"

    # Text-to-SQL with Schema RAG (ML-5.4)
    analytics_sql_enabled: bool = False
    analytics_sql_statement_timeout_ms: int = 5000
    analytics_sql_max_query_cost: int = 10000
    analytics_sql_max_result_rows: int = 100
    analytics_sql_example_retrieval_k: int = 5
    analytics_sql_readonly_dsn: str | None = None

    # Prometheus metrics (OPS-2.1)
    metrics_enabled: bool = True

    # Deep health probes (OPS-2.2)
    health_deep_cache_ttl_seconds: float = 5.0

    # Auth audit log (OPS-4.3)
    auth_audit_enabled: bool = True
    auth_audit_retention_days: int = 90

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
