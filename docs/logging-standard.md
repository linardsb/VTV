# Logging Standard: Hybrid Dotted Namespace Pattern

## Format Specification

**Pattern:** `{domain}.{component}.{action}_{state}`

Where:
- **domain**: Top-level category (application, request, database, agent, external, system)
- **component**: Subsystem or feature (lifecycle, http, connection, tool, llm, etc.)
- **action_state**: Descriptive operation with state using snake_case

**Examples:**
- `application.lifecycle.started`
- `request.http_received`
- `database.connection_initialized`
- `agent.tool.execution_started`

## Why This Pattern?

Based on comprehensive research of OpenTelemetry standards and AI agent frameworks (2024-2025):

1. **OpenTelemetry Compliant** - Follows official semantic conventions
2. **Scalable Hierarchy** - Supports multi-level event taxonomies
3. **Grep-Friendly** - Easy to search with `grep "database\."` or `grep "_failed"`
4. **AI-Parseable** - Clear hierarchical relationships for LLM understanding
5. **State Machine Tracking** - Natural expression of lifecycle transitions
6. **Industry Standard** - Matches Elastic, OTel, LangChain, AWS patterns

## Event Taxonomy

### Application Domain

Application-level lifecycle and system events.

```
application.
├── lifecycle.started          # Application started successfully
├── lifecycle.stopped          # Application shut down gracefully
├── lifecycle.restarting       # Application restarting
├── config.loaded              # Configuration loaded successfully
├── config.validation_failed   # Configuration validation error
└── initialization_failed      # Fatal startup error
```

**Examples:**
```python
logger.info("application.lifecycle.started",
           app_name=settings.app_name,
           version=settings.version,
           environment=settings.environment)

logger.error("application.config.validation_failed",
            error="Invalid DATABASE_URL format",
            exc_info=True)
```

### Request Domain

HTTP request/response lifecycle tracking.

```
request.
├── http_received              # Request received (use instead of "started")
├── http_processing            # Request being processed
├── http_completed             # Request completed successfully
├── http_failed                # Request failed with error
├── validation_failed          # Request validation error
├── rate_limited               # Rate limit exceeded
└── timeout_exceeded           # Request timeout
```

**Examples:**
```python
logger.info("request.http_received",
           method=request.method,
           path=request.url.path,
           client_host=request.client.host)

logger.info("request.http_completed",
           method=request.method,
           path=request.url.path,
           status_code=response.status_code,
           duration_ms=duration)

logger.error("request.http_failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration_ms=duration,
            exc_info=True)
```

### Database Domain

Database operations and health monitoring.

```
database.
├── connection_initialized     # Connection pool initialized
├── connection_established     # Single connection established
├── connection_closed          # Connection closed
├── connection_failed          # Connection failed
├── query_executed             # Query executed successfully
├── query_failed               # Query execution failed
├── transaction_started        # Transaction begun
├── transaction_committed      # Transaction committed
├── transaction_rolled_back    # Transaction rolled back
├── migration_started          # Migration started
├── migration_completed        # Migration completed
├── migration_failed           # Migration failed
├── health_check_passed        # Health check successful
└── health_check_failed        # Health check failed
```

**Examples:**
```python
logger.info("database.connection_initialized",
           pool_size=5,
           max_overflow=10,
           provider="postgresql")

logger.error("database.health_check_failed",
            provider="postgresql",
            exc_info=True)

logger.info("database.query_executed",
           query_type="SELECT",
           table="users",
           duration_ms=45.2)
```

### Health Domain

Health check and readiness monitoring.

```
health.
├── check_passed               # Generic health check passed
├── check_failed               # Generic health check failed
├── readiness_check_passed     # Readiness check passed
├── readiness_check_failed     # Readiness check failed
├── liveness_check_passed      # Liveness check passed
├── liveness_check_failed      # Liveness check failed
└── deep.
    ├── check_completed        # Deep health check completed (fields: status, duration_ms)
    ├── probe_completed        # Individual probe completed (fields: probe, status, latency_ms)
    └── probe_failed           # Individual probe failed (fields: probe, error)
```

**Examples:**
```python
logger.info("health.readiness_check_passed",
           database="connected",
           cache="connected",
           environment=settings.environment)

logger.error("health.readiness_check_failed",
            component="database",
            reason="connection timeout",
            exc_info=True)
```

### Agent Domain

AI agent operations, chat pipeline, tools, and resilience.

```
agent.
├── create_completed                        # Agent instance created (fields: model)
├── error                                   # Unhandled agent error (fields: error, error_type)
├── chat_started                            # Chat pipeline begun (fields: run_id, provider)
├── chat_completed                          # Chat pipeline completed (fields: run_id, duration_ms)
├── chat_failed                             # Chat pipeline error (fields: run_id, error, error_type)
├── chat.selected                           # Agent selected for chat (fields: agent_type)
├── chat.confidence_reroute                 # Confidence-based reroute (fields: from_agent, to_agent)
├── chat.confidence_reroute_failed          # Reroute failed (fields: error)
├── injection.blocked                       # Input blocked by injection filter (fields: pattern)
├── output_validation.blocked               # Output blocked by safety filter (fields: violation_type)
├── output_validation.validator_error       # Validator itself errored (fields: error)
├── response_validation_warning             # Response validation issue (fields: warning)
├── quota_exceeded                          # Daily query quota exceeded (fields: client_ip)
├── quota_exceeded_http                     # Quota exceeded on HTTP request (fields: client_ip, remaining)
├── rag_routing                             # RAG vs direct decision (fields: decision, score)
├── router.decision                         # Multi-agent routing decision (fields: prompt_hash, chosen_agent)
├── correction.
│   ├── triggered                           # Self-correction loop started (fields: run_id, reason)
│   ├── resolved                            # Correction succeeded (fields: run_id, attempt)
│   ├── exhausted                           # Max correction attempts reached (fields: run_id, attempts)
│   ├── failed                              # Correction loop errored (fields: run_id, error)
│   └── metric                              # Correction metrics recorded (fields: provider, attempts)
├── pipeline.
│   ├── run_started                         # Pipeline run started (fields: run_id)
│   ├── run_completed                       # Pipeline run completed (fields: run_id, duration_ms)
│   ├── stopped                             # Pipeline stopped early (fields: run_id, reason)
│   ├── phase_started                       # Pipeline phase started (fields: phase)
│   ├── phase_completed                     # Pipeline phase completed (fields: phase, duration_ms)
│   ├── phase_failed                        # Pipeline phase failed (fields: phase, error)
│   └── summary                             # End-of-pipeline summary (fields: phases, duration_ms)
├── provider_chain.
│   ├── preempted                           # Provider preempted by health check (fields: provider)
│   ├── fallback                            # Falling back to next provider (fields: from_provider, to_provider)
│   └── exhausted                           # All providers failed (fields: providers_tried)
├── provider_health.record_failed           # Health recording error (fields: provider, error)
├── config.
│   ├── model_configured                    # Model provider configured (fields: tier, model)
│   ├── anthropic_api_key_missing           # Anthropic key not set
│   ├── google_api_key_missing              # Google key not set
│   ├── groq_api_key_missing               # Groq key not set
│   └── tier_api_key_missing               # Tier-specific key not set (fields: tier, provider)
├── memory.
│   ├── recall_injected                     # Memories injected into context (fields: count, types)
│   └── recall_failed                       # Memory recall error (fields: error)
├── knowledge.
│   ├── search_started                      # Knowledge search begun (fields: query)
│   ├── search_completed                    # Knowledge search completed (fields: result_count)
│   ├── search_failed                       # Knowledge search error (fields: error)
│   └── search_skipped                      # Knowledge search skipped (fields: reason)
├── skills_load_failed                      # Skills loading error (fields: error)
├── l3_skills_load_failed                   # L3 skills loading error (fields: error)
├── skills.
│   ├── manage_started                      # Skill management tool invoked (fields: action)
│   ├── manage_failed                       # Skill management failed (fields: error)
│   ├── list_completed                      # Skill listing completed (fields: count)
│   └── create_completed                    # Skill created via agent (fields: skill_id)
├── skill_loader.
│   ├── loaded                              # Skill file loaded (fields: path)
│   ├── read_failed                         # Skill file read error (fields: path)
│   ├── missing_front_matter                # Skill missing YAML front matter (fields: path)
│   ├── unterminated_front_matter           # Skill front matter not terminated (fields: path)
│   ├── yaml_parse_failed_or_not_mapping    # YAML parse error (fields: path)
│   ├── invalid_priority_type               # Invalid priority type (fields: path)
│   ├── invalid_priority_value              # Invalid priority value (fields: path)
│   ├── path_escaped                        # Path escaped allowed directory (fields: path)
│   ├── resolve_failed                      # Skill resolution failed (fields: path)
│   └── discover_failed                     # Skill discovery error (fields: domain)
├── analytics_sql.
│   ├── started                             # SQL analytics query started (fields: query_hash)
│   ├── completed                           # SQL analytics query completed (fields: duration_ms)
│   ├── failed                              # SQL analytics query failed (fields: error)
│   ├── cost_exceeded                       # Query cost exceeds limit (fields: estimated_cost)
│   ├── validation_failed                   # SQL validation failed (fields: reason)
│   └── validation_rejected                 # SQL rejected by validator (fields: reason)
├── validation.
│   ├── extract_tool_returns_failed         # Tool return extraction error (fields: error)
│   └── static_cache_unavailable            # Static validation cache miss (fields: reason)
├── registry.close_failed                   # Agent registry cleanup error (fields: error)
├── predict_eta.                            # ML-2.3 ETA prediction agent tool
│   ├── started                             # Tool invocation started (fields: vehicle_id, stop_id)
│   ├── completed                           # Prediction returned (fields: vehicle_id, stop_id, fallback, duration_ms)
│   └── failed                              # Tool error (fields: error, error_type, duration_ms)
├── predict_passenger_load.                 # ML-3.3 load prediction agent tool
│   ├── started                             # Tool invocation started (fields: vehicle_id, stop_id)
│   ├── completed                           # Prediction returned (fields: vehicle_id, stop_id, fallback, duration_ms)
│   └── failed                              # Tool error (fields: error, error_type, duration_ms)
└── circuit_breaker.                        # AI-8.1 LLM provider fast-fail
    ├── half_opened                         # OPEN -> HALF_OPEN (fields: provider, elapsed_s)
    ├── closed                              # HALF_OPEN -> CLOSED (fields: provider, successful_probes)
    ├── rejected                            # Call blocked by OPEN breaker (fields: provider, state)
    ├── probe_success                       # Successful probe in HALF_OPEN (fields: provider)
    └── probe_failure                       # Failed probe in HALF_OPEN (fields: provider)
```

**Examples:**
```python
logger.info("agent.chat_started",
           run_id=run_id,
           provider="anthropic")

logger.info("agent.pipeline.summary",
           phases=["routing", "recall", "chat"],
           duration_ms=2341)

logger.error("agent.correction.failed",
            run_id=run_id,
            exc_info=True)
```

### Transit Domain

Multi-feed GTFS-RT polling, weather/traffic ETL, WebSocket streaming, and anomaly detection.

```
transit.
├── poller.
│   ├── lifecycle_started                   # Poller system started
│   ├── started                             # Single feed poll cycle (fields: feed_id, interval_seconds)
│   ├── all_started                         # All pollers launched (fields: feed_count)
│   ├── all_stopped                         # All pollers stopped
│   ├── cycle_completed                     # Feed poll cycle completed (fields: feed_id, vehicles)
│   ├── fetch_failed                        # Feed fetch error (fields: feed_id, error)
│   ├── leader_elected                      # Redis leader lock acquired (fields: worker_id)
│   ├── leader_election_failed              # Leader election error (fields: error)
│   ├── leader_refresh_failed               # Leader lock refresh error (fields: error)
│   ├── leader_refresh_setup_failed         # Leader refresh setup error (fields: error)
│   ├── leader_refresh_cleanup_error        # Leader refresh cleanup error
│   ├── leader_release_failed               # Leader lock release error
│   ├── not_leader                          # Worker is not leader, skipping
│   ├── disabled                            # Polling disabled by config
│   ├── feed_registered                     # Feed registered for polling (fields: feed_id)
│   ├── history_write_completed             # Historical positions written (fields: count)
│   ├── history_write_failed                # Historical write error (fields: error)
│   ├── redis_write_failed                  # Redis cache write error (fields: error)
│   ├── redis_unavailable                   # Redis not available for caching
│   ├── pubsub_publish_failed               # Pub/Sub publish error (fields: error)
│   └── task_cleanup_error                  # Task cleanup error
├── feed.
│   └── circuit_open                        # Per-feed circuit breaker open, poll skipped (fields: feed_id, retry_after)
├── scraper.
│   ├── fetch_completed                     # Scraper feed fetch completed (fields: feed_id, raw_count, valid_count, duration_ms)
│   └── vehicle_invalid                     # Scraper vehicle skipped validation (fields: feed_id, reason)
├── gps_text.
│   ├── fetch_completed                     # GPS text feed fetch completed (fields: feed_id, raw_lines, valid_count, duration_ms)
│   ├── line_malformed                      # GPS text line has insufficient fields (fields: feed_id, reason, field_count)
│   └── vehicle_invalid                     # GPS text vehicle skipped validation (fields: feed_id, reason)
├── weather.
│   ├── lifecycle_started                   # Weather ETL started
│   ├── lifecycle_stopped                   # Weather ETL stopped
│   ├── lifecycle_disabled                  # Weather ETL disabled by config
│   ├── cycle_completed                     # Weather poll cycle completed
│   ├── cycle_failed                        # Weather poll cycle failed (fields: error)
│   ├── leader_acquired                     # Weather leader lock acquired (fields: worker_id)
│   ├── not_leader                          # Not weather leader, skipping
│   ├── leader_refresh_failed               # Weather leader lock refresh error
│   ├── leader_release_failed               # Weather leader lock release error
│   ├── backfill_started                    # Weather backfill started (fields: days)
│   ├── backfill_completed                  # Weather backfill completed
│   ├── backfill_skipped                    # Weather backfill skipped (fields: reason)
│   ├── pull_completed                      # Weather data pull completed
│   ├── phenomena_fetch_failed              # Weather phenomena fetch error
│   ├── row_skipped                         # Weather row skipped (invalid data)
│   ├── response_too_large                  # Weather API response too large
│   └── circuit_open                        # Weather circuit breaker open
├── traffic.
│   ├── lifecycle_started                   # Traffic ETL started
│   ├── lifecycle_stopped                   # Traffic ETL stopped
│   ├── lifecycle_disabled                  # Traffic ETL disabled by config
│   ├── cycle_completed                     # Traffic poll cycle completed
│   ├── cycle_failed                        # Traffic poll cycle failed (fields: error)
│   ├── leader_acquired                     # Traffic leader lock acquired (fields: worker_id)
│   ├── not_leader                          # Not traffic leader, skipping
│   ├── leader_refresh_failed               # Traffic leader lock refresh error
│   ├── leader_release_failed               # Traffic leader lock release error
│   ├── next_run                            # Next traffic run scheduled (fields: delay_s)
│   ├── counts_pull_completed               # Traffic counts pull completed
│   ├── counts_response_too_large           # Traffic counts response too large
│   ├── count_row_skipped                   # Traffic count row skipped
│   ├── accidents_pull_completed            # Traffic accidents pull completed
│   ├── accidents_response_too_large        # Traffic accidents response too large
│   ├── accident_row_skipped                # Traffic accident row skipped
│   ├── backfill_counts_started             # Traffic counts backfill started
│   ├── backfill_counts_completed           # Traffic counts backfill completed
│   ├── backfill_counts_skipped             # Traffic counts backfill skipped
│   ├── backfill_accidents_started          # Traffic accidents backfill started
│   ├── backfill_accidents_completed        # Traffic accidents backfill completed
│   ├── backfill_accidents_skipped          # Traffic accidents backfill skipped
│   └── circuit_open                        # Traffic circuit breaker open
├── ws.
│   ├── connected                           # WebSocket client connected (fields: user_id, active_count)
│   ├── disconnected                        # WebSocket client disconnected (fields: user_id)
│   ├── auth_failed                         # WebSocket auth rejected (fields: reason)
│   ├── connection_limit_reached            # Max connections reached (fields: limit)
│   ├── subscriber_started                  # Pub/Sub subscriber started
│   ├── subscriber_stopped                  # Pub/Sub subscriber stopped
│   ├── subscriber_stop_error               # Subscriber stop error
│   ├── subscriber_cleanup_error            # Subscriber cleanup error
│   ├── subscriber_reconnecting             # Subscriber reconnecting
│   ├── subscriber_message_parse_failed     # Subscriber message parse error
│   ├── subscribe_updated                   # Client subscription updated (fields: feeds)
│   ├── subscribe_validation_failed         # Subscription validation failed
│   ├── broadcast_completed                 # Broadcast completed (fields: client_count)
│   ├── broadcast_client_disconnected       # Client disconnected during broadcast
│   ├── broadcast_client_error              # Client error during broadcast
│   └── unexpected_error                    # Unexpected WebSocket error
├── train_ws.
│   ├── listener_started                    # Train WS listener task created
│   ├── listener_stopped                    # Train WS listener gracefully stopped
│   ├── listener_stop_error                 # Train WS listener stop error
│   ├── connected                           # Connected to PV train WS (fields: url)
│   ├── first_message                       # First raw message logged for format discovery (fields: raw_snippet)
│   ├── message_received                    # Train positions processed (fields: count)
│   ├── message_parse_failed                # Train WS message parse error (fields: error, raw_snippet)
│   ├── redis_write_failed                  # Train Redis write error (fields: error)
│   ├── history_write_completed             # Train history written to TimescaleDB (fields: records_inserted)
│   ├── history_write_failed                # Train history write error (fields: error)
│   ├── pubsub_publish_failed               # Train Pub/Sub publish error (fields: error)
│   └── reconnecting                        # Train WS reconnecting after error (fields: error, backoff_seconds)
├── publisher.
│   ├── build_started                       # GTFS-RT combined feed build started (fields: feed_id)
│   ├── build_completed                     # GTFS-RT combined feed build completed (fields: vehicle_count, feed_id, bytes_size)
│   ├── build_failed                        # GTFS-RT combined feed build error (fields: feed_id, error)
│   └── cache_hit                           # GTFS-RT combined feed served from cache (fields: feed_id)
├── anomaly.off_route.
│   ├── lifecycle_started                   # Off-route evaluator started
│   ├── lifecycle_stopped                   # Off-route evaluator stopped
│   ├── lifecycle_skipped                   # Off-route evaluator skipped (fields: reason)
│   ├── shutdown_error                      # Off-route evaluator shutdown error
│   ├── cycle_completed                     # Off-route check cycle completed
│   ├── cycle_failed                        # Off-route check cycle failed
│   ├── candidate                           # Off-route candidate detected (fields: vehicle_id)
│   ├── fired                               # Off-route anomaly confirmed (fields: vehicle_id)
│   ├── no_corridor                         # No corridor for route (fields: route_id)
│   └── reset                               # Off-route state reset (fields: vehicle_id)
├── api.
│   ├── vehicles_requested                  # Vehicle positions API call (fields: feed_id)
│   ├── vehicle_history_requested           # Vehicle history API call (fields: vehicle_id)
│   ├── vehicle_eta_requested               # ML-2.3 ETA prediction API call (fields: vehicle_id, stop_id)
│   └── route_delay_trend_requested         # Route delay trend API call (fields: route_id)
├── alerts.
│   ├── fetch_completed                     # Service alerts fetched (fields: count)
│   └── serving_stale_cache                 # Serving stale alert cache
├── trip_updates.
│   ├── fetch_completed                     # Trip updates fetched (fields: count)
│   └── serving_stale_cache                 # Serving stale trip update cache
├── vehicle_positions.
│   ├── fetch_completed                     # Vehicle positions fetched (fields: count)
│   └── serving_stale_cache                 # Serving stale vehicle position cache
├── vehicles.
│   ├── fetch_started                       # Transit vehicles fetch started
│   └── fetch_completed                     # Transit vehicles fetch completed
├── eta.
│   ├── requested                           # ML-2.3 ETA prediction requested (fields: vehicle_id, stop_id)
│   └── completed                           # ML-2.3 ETA prediction completed (fields: vehicle_id, stop_id, fallback)
├── historical_importer.
│   ├── backfill_started                    # Historical backfill started
│   ├── backfill_completed                  # Historical backfill completed
│   ├── backfill_dry_run                    # Backfill dry run (fields: snapshot_count)
│   ├── list_snapshots_started              # Listing available snapshots
│   ├── list_snapshots_completed            # Snapshot listing completed (fields: count)
│   ├── snapshot_download_started           # Snapshot download started (fields: url)
│   ├── snapshot_download_completed         # Snapshot download completed
│   ├── snapshot_import_completed           # Snapshot import completed
│   └── snapshot_skipped_duplicate          # Snapshot skipped (already imported)
├── static_store.
│   ├── load_started                        # Static GTFS store loading
│   ├── load_completed                      # Static store loaded (fields: routes, stops, trips)
│   └── load_failed                         # Static store load error (fields: error)
├── static_cache.load_completed             # Static cache loaded
├── check_driver_availability.
│   ├── started                             # Driver availability check started
│   ├── completed                           # Driver availability check completed
│   └── failed                              # Driver availability check failed
├── get_route_schedule.
│   ├── started                             # Route schedule query started
│   ├── completed                           # Route schedule query completed
│   └── failed                              # Route schedule query failed
├── get_adherence_report.
│   ├── started                             # Adherence report started
│   ├── completed                           # Adherence report completed
│   └── failed                              # Adherence report failed
├── query_bus_status.
│   ├── started                             # Bus status query started
│   ├── completed                           # Bus status query completed
│   └── failed                              # Bus status query failed
├── search_stops.
│   ├── started                             # Stop search started
│   ├── completed                           # Stop search completed
│   └── failed                              # Stop search failed
├── ckan.
│   ├── query_started                       # CKAN SQL query started (fields: sql_hash, cached)
│   ├── query_completed                     # CKAN SQL query completed (fields: sql_hash, record_count, elapsed_ms, cached)
│   ├── query_failed                        # CKAN SQL query failed (fields: sql_hash, error, error_type, elapsed_ms)
│   ├── cache_hit                           # CKAN Redis cache hit (fields: sql_hash, record_count)
│   ├── cache_miss                          # CKAN Redis cache miss (fields: sql_hash)
│   ├── cache_error                         # CKAN Redis cache read error (fields: cache_key)
│   ├── cache_set_error                     # CKAN Redis cache write error (fields: cache_key)
│   ├── pagination_needed                   # CKAN response exceeded page size (fields: sql_hash, total_fetched, page_count)
│   ├── rate_limited                        # CKAN request delayed by rate limiter (fields: wait_s)
│   ├── search_stops_started                # Intercity stop search started (fields: query, latitude, longitude, limit)
│   ├── search_stops_completed              # Intercity stop search completed (fields: result_count, duration_ms)
│   ├── search_stops_failed                 # Intercity stop search failed (fields: error, error_type, duration_ms)
│   ├── search_routes_started               # Intercity route search started (fields: query, stop_name)
│   ├── search_routes_completed             # Intercity route search completed (fields: result_count, duration_ms)
│   └── search_routes_failed                # Intercity route search failed (fields: error, error_type, duration_ms)
└── driver_data.db_fallback                 # Fell back to DB for driver data
```

### Shutdown Domain

Graceful shutdown coordinator (OPS-3.1).

```
shutdown.
├── coordinator.
│   ├── no_tasks                            # No tasks registered for shutdown
│   ├── started                             # Graceful shutdown initiated (fields: task_count)
│   └── completed                           # All tasks drained (fields: duration_ms)
├── task.
│   ├── registered                          # Task registered for shutdown (fields: name, timeout_s)
│   ├── drained                             # Task drained successfully (fields: name, duration_ms)
│   ├── timeout                             # Task drain timed out (fields: name, timeout_s)
│   └── failed                              # Task drain error (fields: name, error)
└── report                                  # Final shutdown report (fields: total_tasks, duration_ms)
```

### Jobs Domain

Arq-based durable job queue (OPS-3.2).

```
jobs.
├── worker.
│   ├── started                             # Arq worker started
│   ├── stopped                             # Arq worker stopped
│   ├── compaction_failed                   # Memory compaction job failed (fields: error)
│   ├── promotion_failed                    # Memory promotion job failed (fields: error)
│   └── daily_adherence_failed              # Daily adherence job failed (fields: error)
└── queue.
    ├── lifecycle_started                   # Queue system initialized
    ├── pool_initialized                    # Redis pool created (fields: pool_size)
    ├── pool_closed                         # Redis pool closed
    ├── job_enqueued                        # Job enqueued (fields: job_name)
    └── enqueue_skipped                     # Job enqueue skipped (fields: reason)
```

### Memory Domain

Agent memory storage, compaction, and promotion.

```
memory.
├── lifecycle.
│   ├── tasks_started                       # Background memory tasks started
│   ├── tasks_stopped                       # Background memory tasks stopped
│   ├── promotion_completed                 # Episodic-to-procedural promotion done (fields: promoted_count)
│   ├── compaction_completed                # Memory compaction completed (fields: compacted_count)
│   ├── disabled                            # Memory system disabled by config
│   └── deferred_to_queue                   # Task deferred to durable queue (fields: task)
├── bridge.
│   ├── episode_persisting                  # Episode being persisted (fields: run_id)
│   ├── episode_stored                      # Episode persisted (fields: run_id)
│   └── storage_failed                      # Fire-and-forget storage error (fields: error)
├── service.
│   ├── store_completed                     # Memory stored (fields: memory_id)
│   ├── store_duplicate_skipped             # Duplicate memory skipped (fields: content_hash)
│   ├── recall_completed                    # Memory recall completed (fields: count)
│   ├── recall_by_query_completed           # Query-based recall completed (fields: count)
│   ├── compact_completed                   # Service-level compaction completed
│   ├── promote_completed                   # Service-level promotion completed
│   ├── delete_decayed_completed            # Decayed memories cleaned (fields: count)
│   ├── llm_merge_completed                 # LLM-based intent merge completed
│   └── llm_merge_failed                    # LLM merge failed (fields: error)
└── repository.
    ├── apply_decay_completed               # Decay applied to memories (fields: count)
    ├── delete_decayed_completed            # Decayed entries deleted (fields: count)
    └── merge_entries_completed             # Memory entries merged (fields: count)
```

### Cache Domain

Cache invalidation (OPS-3.3).

```
cache.
├── invalidation.performed                  # Cache keys invalidated (fields: namespace, count)
└── invalidation.failed                     # Cache invalidation error (fields: namespace, error)
```

### Redis Domain

Redis connection lifecycle.

```
redis.
├── connection_initialized                  # Redis connection established (fields: redis_url)
├── connection_closed                       # Redis connection closed
└── health_check_failed                     # Redis health check failed (fields: error)
```

### Application Domain (Extended)

Application-level lifecycle events (actual events in code).

```
application.
├── lifecycle_started                       # Application started (fields: app_name)
└── lifecycle_stopped                       # Application stopped (fields: app_name)

app.
└── error                                   # Unhandled application error (fields: error)
```

### Rate Limiting Domain

```
rate_limit.
├── redis_unavailable                       # Redis unavailable for rate limiting
└── identity.decode_failed                  # Rate limit identity decode error
```

### RBAC Domain

```
rbac.
├── scope.resolved                          # RBAC scope resolved (fields: user_id, scope)
├── scope.denied                            # RBAC scope denied (fields: user_id, scope)
└── assignment.
    ├── create_completed                    # RBAC assignment created (fields: user_id, scope)
    ├── delete_completed                    # RBAC assignment deleted (fields: user_id, scope)
    └── bulk_replace_completed              # RBAC assignments bulk replaced (fields: user_id, count)
```

### Auth Audit Domain

```
auth.
└── audit.
    ├── denied                              # WARNING — Authorization denial persisted to audit trail (fields: request_id, user_id, path, method, status_code, reason, enforcement_layer)
    └── persist_failed                      # DEBUG — Fire-and-forget DB write failed (fields: exc_info)
```

### Anomaly Routing Domain

```
anomaly.
├── router.alert_created                    # Anomaly alert created (fields: anomaly_type)
└── router.cooldown_suppressed              # Alert suppressed by cooldown (fields: anomaly_type)
```

### Security Domain

```
security.
└── cors_wildcard_with_credentials          # CORS wildcard with credentials detected
```

### Resilience Domain

```
resilience.
└── circuit_breaker.state_changed           # Circuit breaker state transition (fields: provider, state)
```

### External Domain

External API calls and third-party service interactions.

```
external.
├── api.call_started           # External API call started
├── api.call_completed         # API call completed
├── api.call_failed            # API call failed
├── api.rate_limited           # External rate limit hit
├── webhook.received           # Webhook received
├── webhook.processed          # Webhook processed
└── webhook.failed             # Webhook processing failed
```

**Examples:**
```python
logger.info("external.api.call_completed",
           provider="openai",
           endpoint="/v1/chat/completions",
           status=200,
           duration_ms=1245.5)

logger.error("external.api.call_failed",
            provider="stripe",
            endpoint="/v1/charges",
            status=503,
            retry_attempt=1,
            exc_info=True)
```

### Feature Domains (Standard CRUD Pattern)

Feature domains follow a standard `{domain}.{entity}.{action}_{state}` pattern.
Not every event is listed individually -- the pattern itself is the specification.
Domain-specific events beyond CRUD are listed in subsections below.

**Standard CRUD actions** (apply to all feature domains):
```
{domain}.{entity}.
├── fetch_started / fetch_completed / fetch_failed
├── list_started / list_completed
├── create_started / create_completed / create_failed
├── update_started / update_completed / update_failed
└── delete_started / delete_completed / delete_failed
```

**Domains following this pattern:**
alerts, analytics, auth, compliance, drivers, eticket, events, fleet,
geofences, knowledge, ml, obsidian, public_api, schedules, skills, stops, vehicles

## Standard States

Use these standard state suffixes consistently:

| State | Usage | Example |
|-------|-------|---------|
| `_started` | Operation initiated | `tool.execution_started` |
| `_progress` | Operation in progress | `tool.execution_progress` |
| `_completed` | Operation successful | `tool.execution_completed` |
| `_failed` | Operation failed | `tool.execution_failed` |
| `_validated` | Validation successful | `input.validation_validated` |
| `_rejected` | Validation failed | `input.validation_rejected` |
| `_retrying` | Retry attempt | `api.call_retrying` |
| `_cancelled` | Operation cancelled | `request.http_cancelled` |
| `_timeout` | Operation timed out | `request.http_timeout` |
| `_received` | Event received | `request.http_received` |
| `_sent` | Event sent | `notification.email_sent` |

## Depth Guidelines

- **Level 1 (Domain):** Broad system category - `agent`, `request`, `database`
- **Level 2 (Component):** Specific subsystem - `tool`, `llm`, `http`
- **Level 3 (Operation):** Detailed action - `execution_started`, `call_completed`
- **Level 4 (Optional):** Sub-operation - `agent.tool.web_search.execution_started`

**Maximum recommended depth:** 4 levels
**Minimum recommended depth:** 3 levels (domain.component.action_state)

## Required Log Attributes

Always include these context fields:

### All Logs
- `timestamp` - ISO 8601 timestamp (automatic)
- `level` - Log level (automatic)
- `request_id` - Request correlation ID (automatic via middleware)

### Application Logs
- `app_name` - Application name
- `version` - Application version
- `environment` - Environment (development/staging/production)

### Request Logs
- `method` - HTTP method
- `path` - Request path
- `status_code` - Response status
- `duration_ms` - Request duration in milliseconds
- `client_host` - Client IP/host

### Database Logs
- `provider` - Database provider (postgresql, mysql, etc.)
- `duration_ms` - Query duration
- `pool_size` - Connection pool size (when relevant)

### Error Logs
- `error` - Error message
- `error_type` - Error class name
- `exc_info` - Set to `True` for stack traces
- `retryable` - Whether error is retryable (boolean)
- `retry_count` - Number of retry attempts

### Agent Logs
- `agent_id` - Agent instance ID
- `run_id` - Execution run ID
- `tool` - Tool name
- `model` - LLM model name
- `tokens_prompt` - Prompt token count
- `tokens_completion` - Completion token count
- `cost_usd` - Estimated cost

## Usage Examples

### Basic Logging Pattern

```python
from app.core.logging import get_logger

logger = get_logger(__name__)

# Simple event
logger.info("user.registration_started", email=email, source="web")

# With duration tracking
import time
start = time.time()
# ... do work ...
duration_ms = (time.time() - start) * 1000
logger.info("user.registration_completed",
           email=email,
           user_id=user.id,
           duration_ms=round(duration_ms, 2))

# Error logging
try:
    result = perform_operation()
except ValueError as e:
    logger.error("operation.validation_failed",
                error=str(e),
                error_type="ValueError",
                input_value=value,
                exc_info=True)  # Include stack trace
    raise
```

### Lifecycle Pattern

```python
# Start
logger.info("process.execution_started", process_id=id, params=params)

try:
    # Progress updates
    logger.info("process.execution_progress",
               process_id=id,
               step=1,
               total_steps=5)

    # Success
    result = execute()
    logger.info("process.execution_completed",
               process_id=id,
               result_count=len(result),
               duration_ms=duration)

except Exception as e:
    # Failure
    logger.error("process.execution_failed",
                process_id=id,
                error=str(e),
                error_type=type(e).__name__,
                retryable=is_retryable(e),
                exc_info=True)
    raise
```

### Correlation Pattern

```python
# Use request_id for correlation (automatic in middleware)
logger.info("request.http_received", method="POST", path="/api/orders")
logger.info("order.process_started", order_id=123)
logger.info("order.payment_completed", order_id=123, amount=99.99)
logger.info("order.process_completed", order_id=123)
logger.info("request.http_completed", status_code=201)

# All logs will have the same request_id automatically
```

## Query Patterns

### Grep Examples

```bash
# All agent events
grep '"event":"agent\.' logs.json

# All tool operations
grep '"event":"agent\.tool\.' logs.json

# Failed events across system
grep '_failed"' logs.json

# Specific request trace
grep '"request_id":"req-789"' logs.json | jq -r '.event'

# Performance issues (>1000ms)
grep 'duration_ms' logs.json | jq 'select(.duration_ms > 1000)'

# All database errors
grep '"event":"database\.' logs.json | grep '"level":"error"'
```

### Analysis with jq

```bash
# Count events by type
cat logs.json | jq -r '.event' | sort | uniq -c | sort -rn

# Average duration by endpoint
cat logs.json | jq -s 'group_by(.path) | map({path: .[0].path, avg_duration: (map(.duration_ms) | add / length)})'

# Error rate by domain
cat logs.json | jq -r 'select(.level == "error") | .event' | cut -d'.' -f1 | sort | uniq -c
```

## Migration from Old Pattern

### Old Pattern (feature.action.status)
```python
logger.info("request.started")
logger.info("product.create.completed")
logger.error("database.health_check.failed")
```

### New Pattern (domain.component.action_state)
```python
logger.info("request.http_received")
logger.info("product.create_completed")
logger.error("database.health_check_failed")
```

### Key Changes
1. **Underscores in final segment**: `.completed` → `_completed`
2. **Specific component names**: `request.*` → `request.http_*`
3. **Descriptive actions**: `started` → `received`, `initialized`, etc.
4. **Consistent depth**: Minimum 3 levels (domain.component.action_state)

## Do's and Don'ts

### ✅ DO
- Use structured logging with keyword arguments
- Include context (IDs, values, durations)
- Log lifecycle events (started, completed, failed)
- Use `exc_info=True` for errors
- Follow the naming taxonomy
- Include performance metrics (duration_ms)
- Log business-relevant events

### ❌ DON'T
- Use string formatting or f-strings in event names
- Log sensitive data (passwords, tokens, PII)
- Spam logs in tight loops (aggregate instead)
- Use vague event names ("processing", "handling")
- Mix naming patterns
- Skip error context
- Log at wrong levels (debug vs info vs error)
- Create deep hierarchies (>4 levels)

## Type Annotations

All logging calls should use proper type hints:

```python
from typing import Any
import structlog
from structlog.typing import WrappedLogger

logger: WrappedLogger = get_logger(__name__)

def process_user(user_id: int, email: str) -> None:
    logger.info("user.process_started", user_id=user_id, email=email)
    # ... processing ...
    logger.info("user.process_completed", user_id=user_id)
```

## Testing Logging

```python
import json
from io import StringIO
import pytest

def test_logging_event_format(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that logging follows hybrid pattern."""
    logger = get_logger("test")

    logger.info("user.registration_started", email="test@example.com")

    captured = capsys.readouterr()
    log_data = json.loads(captured.out.strip())

    # Verify format
    assert log_data["event"] == "user.registration_started"
    assert "." in log_data["event"]  # Contains dots
    assert "_" in log_data["event"]  # Contains underscores
    assert log_data["email"] == "test@example.com"
    assert "timestamp" in log_data
    assert log_data["level"] == "info"
```

## References

- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/)
- [Structlog Documentation](https://www.structlog.org/)
- [LangChain Observability](https://python.langchain.com/docs/guides/productionization/logging)
- Research: AI Agent Feedback Loop Optimization (2024-2025)

---

**Last Updated:** 2026-04-13
**Version:** 2.0.0
