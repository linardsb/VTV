# ADR-0003: Redis for Cache Layer

## Status

Accepted

## Context

VTV has three caching needs with different characteristics:

1. **Vehicle position cache** - GTFS-RT feeds polled every 10-30s produce ~200 vehicle positions per feed. These must be readable with sub-ms latency for WebSocket push to connected clients. TTL: 120s.

2. **Embedding cache** - OpenAI embedding API calls cost money and add latency (~200ms per call). The same document chunks are re-embedded during search, rechunking, and eval runs. TTL: 3600s.

3. **Rate limit counters** - slowapi needs a shared counter store that works across multiple Gunicorn workers. Must survive worker restarts.

Alternatives considered:

- **In-process dict** - Fast but not shared across workers. Rate limits would be per-worker (4x the intended limit with 4 workers). Vehicle positions would need to be polled by every worker independently.
- **PostgreSQL** - Adds unnecessary write load for ephemeral data. Position cache writes every 10s would compete with business transactions.
- **Memcached** - Viable but lacks pub/sub for WebSocket fan-out. Would need a second system for real-time push.

## Decision

We use **Redis** (`redis[hiredis]>=5.2.0`) as a unified cache layer, configured in `app/core/redis.py` as an async singleton. Three subsystems share the same Redis instance:

- **Vehicle positions** (`app/transit/poller.py`) - `FeedPoller` writes enriched positions with 120s TTL. `redis_reader.py` reads them. `ws_subscriber.py` uses Redis Pub/Sub for WebSocket fan-out.
- **Embedding cache** (`app/knowledge/embedding.py`) - `CachedEmbeddingProvider` wraps the base provider, caching vectors by content hash with 3600s TTL. Configurable via `embedding_cache_enabled` and `embedding_cache_ttl` in settings.
- **Rate limit storage** (`app/core/rate_limit.py`) - slowapi stores counters in Redis for cross-worker enforcement. Falls back to in-memory storage if Redis is unavailable (unit test mode).

## Consequences

**Easier:**
- Single infrastructure dependency for all caching needs - one connection pool, one health check
- WebSocket fan-out via Pub/Sub without polling or additional message brokers
- Embedding cache reduces API costs proportionally to cache hit rate
- Rate limits enforce correctly across all Gunicorn workers

**Harder:**
- Redis becomes a critical dependency - if it goes down, rate limits fall back to per-worker and vehicle positions stop updating
- Connection pool tuning required under high WebSocket connection counts
- Cache invalidation logic spread across three subsystems (each manages its own TTLs)
