# Review: DMS Enhancements (app/knowledge/)

**Summary:** Solid implementation of OCR detection, tag CRUD, and auto-tagging. All validation passes. Three high-priority issues: tag enrichment gaps in two service methods and a race condition in `get_or_create_tag`. Five medium issues around logging consistency and N+1 queries.

| # | File:Line | Issue | Suggestion | Priority |
|---|-----------|-------|------------|----------|
| 1 | `service.py:237` | `update_document` returns `DocumentResponse.model_validate(doc)` without enriching tags — response always shows `tags: []` even if document has tags | Add tag enrichment (like `get_document` does at line 407-409) before returning | High |
| 2 | `service.py:213-215` | `ingest_document` returns response without auto-generated tags — `db.refresh(doc)` doesn't load tags since no ORM relationship exists | Call `get_document(doc.id)` instead of `model_validate(doc)` at return, or enrich tags manually | High |
| 3 | `repository.py:410-422` | `get_or_create_tag` has TOCTOU race — two concurrent requests could both pass the `get_tag_by_name` check and both attempt `create_tag`, causing a unique constraint violation | Use `pg_insert(Tag.__table__).on_conflict_do_nothing()` + `RETURNING` or catch `IntegrityError` and retry the get | High |
| 4 | `service.py:524-528` | `DocumentNotFoundError` raised for missing tags — semantically incorrect, misleading error type | Create `TagNotFoundError(NotFoundError)` in exceptions.py, or use generic `NotFoundError` directly | Medium |
| 5 | `service.py:440-447` | N+1 query: `list_documents` calls `get_tags_for_document` per document — 20 docs = 21 queries | Batch load: single query joining document_tags + tags filtered by doc IDs, then zip into responses | Medium |
| 6 | `processing.py:136-143` | OCR fallback `logger.warning` missing `error=str(e)` and `error_type=type(e).__name__` per logging convention | Change `except Exception:` to `except Exception as e:` and add error context fields | Medium |
| 7 | `service.py:648-653` | Auto-tag `logger.warning` missing `error=str(e)` and `error_type=type(e).__name__` | Same fix: capture exception as `e` and add structured error fields | Medium |
| 8 | `service.py:153` | Early return path (no chunks) also returns response without tags — `DocumentResponse.model_validate(doc)` | Enrich with tags or call `get_document(doc.id)` | Medium |
| 9 | `service.py:510` | Lazy import of `DuplicateTagError` inside method body — already importable at module level | Move to top-level imports (it's in the same package) | Low |
| 10 | `service.py:186` | Inner exception handler `logger.error("knowledge.ingest.status_update_failed")` missing `exc_info=True` — swallows the reason the status update failed | Add `exc_info=True` to the logger call | Low |
| 11 | `repository.py:431-437` | `add_tags_to_document` executes N individual INSERT statements (one per tag_id) | Batch into single `pg_insert` with multiple VALUES rows | Low |

**Priority Guide:**
- **Critical**: Type safety violations, security issues, data corruption risks
- **High**: Data inconsistency (stale responses), race conditions, broken patterns
- **Medium**: Missing logging context, N+1 queries, semantic mismatches
- **Low**: Import style, minor optimizations

**Stats:**
- Files reviewed: 11 (7 source + 4 test)
- Issues: 11 total — 0 Critical, 3 High, 5 Medium, 3 Low

**Notes:**
- All 8 security checks pass — auth on every endpoint, file sanitization, path traversal protection, rate limiting, streaming upload size limit
- Type safety clean — only 1 justified `type: ignore[redundant-cast]` (mypy/pyright conflict) and 1 pre-existing `type: ignore[prop-decorator]`
- Test coverage good: 71 knowledge tests across 5 test files
- Migration is clean with proper server_default for existing rows
