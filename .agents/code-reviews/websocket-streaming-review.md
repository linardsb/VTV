# Code Review: WebSocket Live Streaming

**Target:** `app/transit/ws_*.py`, `app/transit/poller.py` (changes), `app/main.py` (changes), `nginx/nginx.conf` (changes), `app/transit/tests/test_ws_*.py`, `app/transit/tests/test_poller.py` (additions)

**Summary:** Solid implementation with clean architecture, good test coverage (21 new tests), and proper error isolation. Two high-priority issues: idle connections will be killed by the receive timeout (protocol expects client messages but only defines server-to-client pings), and auth close reasons leak token status information.

## Findings

| # | File:Line | Issue | Suggestion | Priority |
|---|-----------|-------|------------|----------|
| 1 | `ws_routes.py:104-108` | **Receive timeout kills idle connections.** `asyncio.wait_for(receive_text(), timeout=heartbeat+10)` expects client messages every ~40s. But the protocol only defines server→client pings; no pong action is handled. Clients that subscribe once and only receive pushes will be disconnected after 40s of silence. | Remove the `wait_for` timeout from the message loop. Use WebSocket protocol-level ping/pong (`websocket.send({"type": "websocket.ping"})`) handled at the Starlette layer for keepalive, or make the receive a `select()` between a heartbeat event and receive. Alternatively, accept `{"action": "pong"}` from clients and document the requirement. | High |
| 2 | `ws_routes.py:68-80` | **Auth close reasons leak token state.** Three distinct reasons — "Missing token", "Invalid token", "Token revoked" — allow an attacker to distinguish between no token, bad token, and previously-valid-but-revoked token. "Token revoked" confirms a token was once valid. | Use a single generic reason for all auth failures: `await websocket.close(code=4001, reason="Authentication failed")`. Keep the specific reason only in the structured log event (already logged with `reason=` kwarg). | Medium |
| 3 | `ws_routes.py:83-89` | **Connection registered before accept.** `manager.connect()` is called before `websocket.accept()`. Between these two awaits, the ConnectionManager considers this client "connected" and may try to `broadcast()` to it via the subscriber. Sending to a not-yet-accepted WebSocket raises an error (caught by broadcast error handling, but causes noise). | Move `manager.connect()` after `await websocket.accept()`, or gate `broadcast()` sends on an "accepted" flag in `_ClientSubscription`. | Medium |
| 4 | `ws_schemas.py:89` | **`WsAck.action` uses bare `str` instead of `Literal`.** Per VTV convention, constrained string fields must use `Literal[...]` types. The action field is always one of "connected", "subscribe", "unsubscribe". | Change to `action: Literal["connected", "subscribe", "unsubscribe"]` and add import. | Medium |
| 5 | `ws_routes.py:103` | **No `ws_enabled` check in endpoint.** The lifespan conditionally starts the subscriber when `ws_enabled=False`, but the endpoint is always registered. Clients can connect, authenticate, and sit idle receiving nothing — confusing behavior. | Add an early check: `if not settings.ws_enabled: await websocket.close(code=1013, reason="WebSocket streaming disabled"); return` | Medium |
| 6 | `nginx/nginx.conf:263` | **No connection limit on `/ws/` location.** Without `limit_conn`, a single IP can open unlimited TCP connections to the WebSocket endpoint before JWT auth runs (auth happens at the application level, after TCP/TLS handshake). | Add `limit_conn addr 10;` inside the `/ws/` location block to limit per-IP concurrent WebSocket connections at the nginx layer. | Medium |
| 7 | `ws_routes.py:134` | **Subscribe validation failure not logged.** Bare `except Exception:` sends error to client but doesn't log. Other error paths consistently log with structured events. | Add `logger.warning("transit.ws.subscribe_validation_failed", user_id=user_id, error=str(e), error_type=type(e).__name__)` inside the except block. | Medium |
| 8 | `ws_routes.py:50` | **Redundant exception tuple.** `except (WebSocketDisconnect, asyncio.CancelledError, Exception)` — `Exception` is a superclass of both `WebSocketDisconnect` and `CancelledError` (in Python 3.14, `CancelledError` inherits from `BaseException`, not `Exception`, so this is NOT redundant for `CancelledError`). However, if `CancelledError` propagation is suppressed here, the heartbeat task can't be properly cancelled. | Change to `except (WebSocketDisconnect, Exception): return` and handle `CancelledError` separately with `raise` to allow propagation. Or use `except BaseException: return` since heartbeat suppression is intentional. | Low |
| 9 | `ws_routes.py:154` | **Untrusted input in error message.** `f"Unknown action: {action}"` includes arbitrary client-provided value. Not a security risk (sent back to same client), but could contain malicious strings in logs if the error message is ever logged. | Truncate: `f"Unknown action: {str(action)[:50]}"` | Low |
| 10 | `ws_subscriber.py:58-59` | **Cleanup error logged at debug level.** `logger.debug("transit.ws.subscriber_cleanup_error")` makes pubsub cleanup failures invisible in production (default INFO). | Change to `logger.warning` for operational visibility during shutdown issues. | Low |
| 11 | `test_ws_routes.py:32,40` | **Broad `pytest.raises(Exception)` with `noqa: B017`.** Tests assert "some exception" but don't verify the specific close code (4001). | Use `starlette.testclient.WebSocketDenialResponse` or catch `WebSocketDisconnect` and assert `code == 4001`. | Low |

## Priority Summary

- **Critical**: 0
- **High**: 1 (receive timeout kills idle connections)
- **Medium**: 6
- **Low**: 4

**Stats:**
- Files reviewed: 11 (4 new source, 3 modified, 4 test files)
- Issues: 11 total — 0 Critical, 1 High, 6 Medium, 4 Low

## Positive Observations

- Clean error isolation in broadcast — one broken client doesn't block others
- Proper exponential backoff with max cap in subscriber reconnection
- Pub/Sub failure in poller is non-blocking (warning logged, polling continues)
- Good test coverage: 21 new tests covering happy path, filtering, auth, reconnect, and error handling
- JWT validation reuses existing `decode_token`/`is_token_revoked` — no duplicated auth logic
- Security convention tests updated correctly (PUBLIC_ALLOWLIST)

## Next Step

To fix issues: `/code-review-fix .agents/code-reviews/websocket-streaming-review.md`
