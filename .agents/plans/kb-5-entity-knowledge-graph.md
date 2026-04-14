# Plan: KB-5 Entity/Knowledge-Graph Overlay

## Context

Transit documents heavily reference shared entities — "Route 22", "Brīvības iela", "EU Regulation 561/2006". When a dispatcher asks about Route 22, chunks mentioning Route 22 should rank higher even if embedding similarity is moderate. Pure hybrid search (vector + BM25 + RRF) undervalues exact-entity co-occurrence because dense embeddings are paraphrase-tolerant and BM25 loses inflections.

KB-5 adds a lightweight entity layer: extract named entities during chunking, store them in `entities` + `entity_mentions` tables, and multiply RRF scores for chunks that share entities with the query. Extraction uses deterministic regex (routes, regulations) plus a GTFS-backed gazetteer (stop names), with optional spaCy NER for people/organizations. The boost is feature-flagged, config-tunable, and fails open (multiplier = 1.0 if extraction errors).

## Security Context Assessment

Applicable contexts from `_shared/security-contexts.md`:

- **CTX-INPUT** — entity extractor consumes user search queries and document text. Regex patterns must avoid ReDoS (use non-greedy bounded quantifiers). Mention-text column needs `max_length` constraint. Entity names stored in DB must be length-bounded.
- **CTX-INFRA** — adding optional spaCy dependency (`[dependency-groups] ner`). Must not break builds when group is not installed; fallback must be automatic and silent.

Not applicable:
- CTX-AUTH (no auth path changes)
- CTX-RBAC (no new endpoints — search endpoint already protected; entity data is server-internal)
- CTX-FILE (no file handling changes; chunking pipeline already validates uploads)
- CTX-AGENT (not an agent tool)

## Research Summary

**Reference features to mirror:**
- `app/knowledge/lemmatizer.py:27-101` (KB-2) — optional-dep + warm-up singleton + `NoopLemmatizer` fallback
- `app/knowledge/feedback.py:64-110` (KB-4) — per-query-type tuning + Redis + fail-open

**RRF injection point — `app/knowledge/service.py:684-707`:**
```python
# Current: RRF fusion (684-697) → temporal boost (699-707) → sort + rerank
# KB-5:    RRF fusion         → temporal boost         → ENTITY BOOST ← NEW → sort + rerank
```
After the temporal-boost loop and before `sorted_ids = sorted(...)`, multiply `chunk_scores[chunk_id]` by an entity-match multiplier computed from the query's extracted entity set vs. `entity_mentions` for each chunk.

**Key files & roles:**
| File | Role | LOC hotspots |
|------|------|--------------|
| `app/knowledge/models.py:30-106` | `Document`, `DocumentChunk`, `Tag` | + `Entity`, `EntityMention` |
| `app/knowledge/schemas.py:143-185` | `SearchRequest`/`SearchResult`/`SearchResponse` | optional `entities` list on result |
| `app/knowledge/service.py:604-811` | `KnowledgeService.search()` | inject boost at ~L708 |
| `app/knowledge/repository.py:315-422` | `search_vector` / `search_fulltext` | + `get_chunk_entity_ids(chunk_ids)` bulk lookup |
| `app/knowledge/chunking.py` | `ChunkResult` dataclass + chunker | call `extract_entities()` inside chunk producer |
| `app/stops/models.py:15-43` | `Stop.stop_name` | gazetteer source for stop-name extractor |
| `app/core/config.py:248-260` | RRF / temporal flags | + `entity_*` flags |

**GTFS stop gazetteer:** `app/stops/models.py:15-43` — `Stop.gtfs_stop_id` + `Stop.stop_name`. Load at startup into a module-level frozenset keyed by case-folded stop name. Singleton pattern same as `_lemmatizer_provider` in `service.py:53-56`.

**Optional-dep pattern (copy from lemmatizer.py):**
- Lazy `from spacy import load` inside `_load()`
- Protocol `EntityExtractor` with sync `extract(text, language) -> list[EntityMention]` + async `warm_up()`
- `RegexEntityExtractor` (always available) + `SpacyEntityExtractor` (optional)
- Module singleton factory `_get_entity_extractor()` that returns Spacy when available+enabled, else Regex
- `pyproject.toml` → `[dependency-groups] ner = ["spacy>=3.7,<4.0"]`

**Shared utilities confirmed available:** `TimestampMixin` (`app.shared.models`), `get_logger` (`app.core.logging`), `get_db_context` (`app.core.database`), `AppError` hierarchy (`app.core.exceptions`), `escape_like` (`app.shared.utils`).

**Not present in repo:** no existing NER / entity code. KB-5 is the first entity module.

## Test Landscape

**Reusable fixtures (from `app/knowledge/tests/`):**
- `make_document`, `make_chunk` — `test_repository.py:15-57`
- `sample_latvian_text`, `sample_english_text` — `conftest.py`
- Redis mock helper pattern — `test_feedback.py:27-33`
- Repo mock pattern — `test_feedback.py:35-51`
- Service mock with `AsyncMock(spec=KnowledgeService)` — `test_routes.py:88-91`

**RRF test template to mirror:** `test_repository.py:278-282` (vector/fulltext tuple unpacking); extend chunk-score assertions to verify boost applied when entity match exists.

**Integration marker convention:** `@pytest.mark.integration` on any test that touches `KnowledgeRepository` or DB session. Unit tests for regex extractor + gazetteer stay unmarked.

**Optional-dep test pattern (from `test_lemmatizer.py:57-74`):**
- Test fallback path with non-existent model (`pytest.raises(FileNotFoundError)`)
- Inject fake pipeline via `provider._pipeline = MagicMock()` to bypass `_load()`
- No `pytest.importorskip` used in repo; follow the try-inject pattern instead.

## Type Check Baseline (must not regress in KB-5 edit targets)

- **pyright:** 60 errors / 0 warnings across `app/knowledge/` — ALL cluster in `lifecycle.py`, `feedback.py`, `tests/test_feedback.py`, `tests/test_versioning.py` (KB-3/KB-4 WIP from parallel sessions). **`repository.py` and `chunking.py` are clean.**
- **mypy:** 19 errors across 4 files (same WIP cluster). **`repository.py` and `chunking.py` are clean.**
- **ruff:** 0 findings.

**Scope rule:** KB-5 must introduce **0 new errors in `app/knowledge/repository.py`, `chunking.py`, `models.py`, `schemas.py`, `service.py`**, and the new files `entity_extractor.py`, `entities_gazetteer.py`. Do not attempt to fix the KB-3/KB-4 baseline errors — they belong to other parallel sessions.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `alembic/versions/e5n6t6k6b6_add_entities.py` | `entities` + `entity_mentions` tables |
| CREATE | `app/knowledge/entity_extractor.py` | `EntityExtractor` protocol + `RegexEntityExtractor` + `SpacyEntityExtractor` + `NoopEntityExtractor` + singleton factory |
| CREATE | `app/knowledge/entities_gazetteer.py` | Startup-loaded frozenset of stop names from `Stop.stop_name`; route-number regex; regulation regex; normalization |
| CREATE | `app/knowledge/tests/test_entity_extractor.py` | Unit tests for extractors (no DB) |
| CREATE | `app/knowledge/tests/test_entity_boost.py` | Service-level RRF + entity boost integration tests |
| UPDATE | `app/knowledge/models.py` | Add `Entity` + `EntityMention` ORM models |
| UPDATE | `app/knowledge/schemas.py` | Add optional `entities: list[str]` on `SearchResult` |
| UPDATE | `app/knowledge/repository.py` | Add `upsert_entities`, `record_mentions`, `get_entity_ids_for_chunks`, `get_entity_ids_for_names` |
| UPDATE | `app/knowledge/service.py` | Call extractor during ingest; apply entity-boost multiplier after temporal boost in `search()` |
| UPDATE | `app/knowledge/chunking.py` | Extend `ChunkResult` dataclass with `entity_mentions: list[ExtractedEntity]` |
| UPDATE | `app/core/config.py` | Add `entity_extraction_enabled`, `entity_boost_enabled`, `entity_boost_multiplier`, `entity_mention_confidence_threshold`, `entity_extractor_provider` |
| UPDATE | `app/knowledge/lifecycle.py` (or startup hook) | Warm up gazetteer + extractor on app start |
| UPDATE | `pyproject.toml` | Add `[dependency-groups] ner = ["spacy>=3.7,<4.0"]` + mypy override + pyright stubs-missing directive |

## Preflight Warnings

From test-scout scan — these pre-existing patterns will break if touched incorrectly:

1. **`app/knowledge/tests/test_repository.py:278-282`** — asserts `results[0][2] < results[1][2]` on the 3-tuple `(chunk, doc, score)` returned by `search_vector`/`search_fulltext`. **Do NOT change the tuple arity.** Keep entity scoring in a side-channel dict; do not extend the repository return type.
2. **`app/knowledge/service.py:725`** — `cid = top_ids[rr.index]` assumes reranker index valid within `top_ids`. Adding a secondary entity-boost filter that changes `top_ids` length before rerank would break this. **Apply boost as a multiplier only, before sort; do not prune.**
3. **Hardcoded "first result" assertions** (`test_repository.py:280`) — `results[0][0].content == "Very relevant text"`. Tests that assert specific ordering in hybrid search may need to be rerun locally to confirm entity boost doesn't reorder; if a test previously passing fails solely due to boost reordering, set `entity_boost_enabled=False` in that test's mock settings rather than rewriting.
4. **Schema field additions break ALL constructors (anti-pattern #11)** — adding `entities: list[str] | None = None` to `SearchResult` requires the field to default to `None` and be optional. Grep for `SearchResult(` before adding to confirm no constructor positional-args break.
5. **Missing type exports used by WIP** — `QueryType`, `RankSource`, `RRFWeights`, `FeedbackChunkNotFoundError` referenced by `feedback.py` but not yet defined. **These are KB-4's problem, not KB-5's.** Do not add them as a side-effect.
6. **Optional untyped lib 3-layer fix (anti-pattern #12)** — spaCy has no published stubs in our environment. Must add on same pass: (a) mypy `[[tool.mypy.overrides]]` with `module = "spacy.*"` + `ignore_missing_imports = true`, (b) pyright file-level `# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false` in `entity_extractor.py`, (c) no ARG001 exemptions needed (no decorators).
7. **Dataclass default factory typing (anti-pattern #24)** — on `ChunkResult`, use `entity_mentions: list[ExtractedEntity] = field(default_factory=list)` — already typed via the field annotation, this is fine. Do NOT write `default_factory=list[ExtractedEntity]`.
8. **Regex ReDoS (CTX-INPUT)** — route regex `maršrut\w*\s+\d+` is bounded and safe. Regulation regex must be bounded: `EU\s+\d{1,4}/\d{2,4}` not `EU\s+.+/.+`. Add `max_length` on input to extractor (clip query to 500 chars before regex).

## Implementation Steps

Files listed in VSA order: migration → models/schemas → gazetteer/extractor → repository → chunking → service → config → tests.

### 1. Migration — `alembic/versions/e5n6t6k6b6_add_entities.py`

Base revision on latest head. Create two tables + indexes.

```python
# Key ops (condensed):
op.create_table(
    "entities",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("entity_type", sa.String(32), nullable=False),  # route, stop, regulation, person, org
    sa.Column("name", sa.String(500), nullable=False),
    sa.Column("normalized_name", sa.String(500), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("entity_type", "normalized_name", name="uq_entities_type_normalized"),
)
op.create_index("ix_entities_type_norm", "entities", ["entity_type", "normalized_name"])

op.create_table(
    "entity_mentions",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
    sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False),
    sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("extraction_method", sa.String(32), nullable=False),  # regex, gazetteer, spacy
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("entity_id", "chunk_id", name="uq_entity_mentions_pair"),
)
op.create_index("ix_entity_mentions_chunk", "entity_mentions", ["chunk_id"])
op.create_index("ix_entity_mentions_entity", "entity_mentions", ["entity_id"])
```

`downgrade()` drops both tables in reverse order.

**Validation:** `uv run alembic upgrade head` (dry-run locally against `make db`), `uv run alembic downgrade -1`, re-upgrade.

### 2. Models — update `app/knowledge/models.py`

Append after existing models:

```python
class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    __table_args__ = (UniqueConstraint("entity_type", "normalized_name"),)

class EntityMention(Base):
    __tablename__ = "entity_mentions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("entity_id", "chunk_id"),)
```

**Validation:** `uv run ruff format app/knowledge/models.py && uv run ruff check app/knowledge/models.py && uv run pyright app/knowledge/models.py && uv run mypy app/knowledge/models.py`

### 3. Schemas — update `app/knowledge/schemas.py`

Add to `SearchResult` only — optional, default None:
```python
entities: list[str] | None = Field(default=None, description="Canonical entity names mentioned in this chunk")
```

New extractor result DTO (non-ORM):
```python
class ExtractedEntity(BaseModel):
    entity_type: Literal["route", "stop", "regulation", "person", "org"]
    name: str = Field(max_length=500)
    normalized_name: str = Field(max_length=500)
    extraction_method: Literal["regex", "gazetteer", "spacy"]
    mention_count: int = Field(ge=1, default=1)
```

**Validation:** `uv run ruff format app/knowledge/schemas.py && uv run ruff check app/knowledge/schemas.py && uv run pyright app/knowledge/schemas.py && uv run mypy app/knowledge/schemas.py`

### 4. Gazetteer — CREATE `app/knowledge/entities_gazetteer.py`

Module-level cached stop-name set + normalization helpers + regex constants.

```python
# Constants (module level)
_ROUTE_RE = re.compile(r"(?:maršrut\w*|route)\s+(\d{1,4}[A-Za-z]?)", re.IGNORECASE)
_REGULATION_RE = re.compile(r"(?:EU|ES|Regulation)\s+(\d{1,4}/\d{2,4})", re.IGNORECASE)

_stop_names_lower: frozenset[str] | None = None

async def load_stop_gazetteer() -> None:
    """Load Stop.stop_name from DB into a case-folded frozenset. Call at startup."""
    global _stop_names_lower
    async with get_db_context() as session:
        result = await session.execute(select(Stop.stop_name))
        names = {row[0].casefold() for row in result.all() if row[0]}
    _stop_names_lower = frozenset(names)
    logger.info("knowledge.gazetteer.loaded", count=len(names))

def get_stop_names() -> frozenset[str]:
    return _stop_names_lower or frozenset()

def normalize_route(raw: str) -> str:
    m = _ROUTE_RE.search(raw)
    return f"route_{m.group(1).lower()}" if m else raw.lower()

def normalize_stop(raw: str) -> str:
    return raw.casefold().strip()

def normalize_regulation(raw: str) -> str:
    m = _REGULATION_RE.search(raw)
    return f"reg_{m.group(1)}" if m else raw.lower()
```

Cap input length: every public extract call must do `text = text[:20000]` before regex to bound worst-case.

**Validation:** `uv run ruff format app/knowledge/entities_gazetteer.py && uv run ruff check app/knowledge/entities_gazetteer.py && uv run pyright app/knowledge/entities_gazetteer.py && uv run mypy app/knowledge/entities_gazetteer.py`

### 5. Extractor — CREATE `app/knowledge/entity_extractor.py`

File-level pyright directive: `# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false`.

Protocol + three implementations + factory:
```python
class EntityExtractor(Protocol):
    async def warm_up(self) -> None: ...
    def extract(self, text: str, language: str) -> list[ExtractedEntity]: ...

class RegexEntityExtractor:
    """Always-available: routes + regulations + gazetteer stops."""
    async def warm_up(self) -> None:
        await load_stop_gazetteer()

    def extract(self, text: str, language: str) -> list[ExtractedEntity]:
        text = text[:20000]  # ReDoS bound
        found: dict[tuple[str, str], ExtractedEntity] = {}
        for m in _ROUTE_RE.finditer(text):
            norm = normalize_route(m.group(0))
            key = ("route", norm)
            found[key] = ExtractedEntity(entity_type="route", name=m.group(0), normalized_name=norm,
                                         extraction_method="regex", mention_count=(found[key].mention_count + 1) if key in found else 1)
        # ...same for regulations
        stops = get_stop_names()
        for stop_name in stops:
            if stop_name and stop_name in text.casefold():
                key = ("stop", stop_name)
                found[key] = ExtractedEntity(entity_type="stop", name=stop_name, normalized_name=stop_name,
                                             extraction_method="gazetteer", mention_count=1)
        return list(found.values())

class SpacyEntityExtractor:
    """Optional: person + org NER. Falls back silently if spaCy missing."""
    def __init__(self, model_name: str = "xx_sent_ud_sm") -> None:
        self._model_name = model_name
        self._nlp: Any | None = None  # noqa: ANN401

    async def warm_up(self) -> None:
        try:
            import spacy
            self._nlp = await asyncio.to_thread(spacy.load, self._model_name)
            logger.info("knowledge.entity_extractor.spacy_loaded", model=self._model_name)
        except Exception as e:
            logger.warning("knowledge.entity_extractor.spacy_unavailable", reason=str(e))
            self._nlp = None

    def extract(self, text: str, language: str) -> list[ExtractedEntity]:
        if self._nlp is None:
            return []
        doc = self._nlp(text[:20000])
        out: list[ExtractedEntity] = []
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG"}:
                ent_type = "person" if ent.label_ == "PERSON" else "org"
                out.append(ExtractedEntity(
                    entity_type=ent_type, name=str(ent.text), normalized_name=str(ent.text).casefold(),
                    extraction_method="spacy", mention_count=1,
                ))
        return out

class NoopEntityExtractor:
    async def warm_up(self) -> None: return
    def extract(self, text: str, language: str) -> list[ExtractedEntity]: return []

# Factory — singleton
_extractor_provider: EntityExtractor | None = None

async def get_entity_extractor() -> EntityExtractor:
    global _extractor_provider
    if _extractor_provider is not None:
        return _extractor_provider
    settings = get_settings()
    if not settings.entity_extraction_enabled:
        _extractor_provider = NoopEntityExtractor()
        return _extractor_provider
    regex = RegexEntityExtractor()
    await regex.warm_up()
    if settings.entity_extractor_provider == "spacy":
        spacy_ext = SpacyEntityExtractor()
        await spacy_ext.warm_up()
        _extractor_provider = CompositeExtractor(regex, spacy_ext)
    else:
        _extractor_provider = regex
    return _extractor_provider
```

`CompositeExtractor` runs both and concatenates; dedupe by `(entity_type, normalized_name)`.

**Validation:** `uv run ruff format app/knowledge/entity_extractor.py && uv run ruff check app/knowledge/entity_extractor.py && uv run pyright app/knowledge/entity_extractor.py && uv run mypy app/knowledge/entity_extractor.py`

### 6. Repository — update `app/knowledge/repository.py`

Add three methods — do NOT change existing `search_vector`/`search_fulltext` return types.

```python
async def upsert_entities(self, entities: list[ExtractedEntity]) -> dict[tuple[str, str], int]:
    """Insert-or-ignore entities; return {(type, normalized_name): id} map."""
    # Use ON CONFLICT DO NOTHING on (entity_type, normalized_name)
    # Then SELECT ids for all (type, normalized_name) pairs

async def record_mentions(self, chunk_id: int, mentions: list[tuple[int, int, str]]) -> None:
    """Bulk insert (entity_id, chunk_id, mention_count, extraction_method).
    ON CONFLICT (entity_id, chunk_id) DO UPDATE SET mention_count = EXCLUDED.mention_count."""

async def get_entity_ids_for_chunks(self, chunk_ids: Sequence[int]) -> dict[int, frozenset[int]]:
    """Bulk: {chunk_id: frozenset(entity_ids)} for all given chunks."""
    # SELECT chunk_id, entity_id FROM entity_mentions WHERE chunk_id IN (...)

async def get_entity_ids_for_names(self, pairs: Sequence[tuple[str, str]]) -> frozenset[int]:
    """Given [(entity_type, normalized_name), ...], return matching entity ids."""
```

**Validation:** `uv run ruff format app/knowledge/repository.py && uv run ruff check app/knowledge/repository.py && uv run pyright app/knowledge/repository.py && uv run mypy app/knowledge/repository.py`

### 7. Chunking — update `app/knowledge/chunking.py`

Extend `ChunkResult` dataclass:
```python
@dataclass(frozen=True, slots=True)
class ChunkResult:
    # ...existing fields
    entity_mentions: tuple[ExtractedEntity, ...] = ()
```
(Use `tuple` not `list` because the dataclass is `frozen=True`; `field(default_factory=...)` not needed for empty tuple default.)

Do NOT call the extractor inside `chunk_text()` itself — keep it pure. Extraction happens in the service at ingest time so the chunker stays sync + dependency-free.

**Validation:** `uv run ruff format app/knowledge/chunking.py && uv run ruff check app/knowledge/chunking.py && uv run pyright app/knowledge/chunking.py && uv run mypy app/knowledge/chunking.py`

### 8. Service — update `app/knowledge/service.py`

**Ingest path (in existing `ingest_document` flow, after chunking + before commit):**
```python
if settings.entity_extraction_enabled:
    extractor = await get_entity_extractor()
    for chunk, chunk_result in zip(persisted_chunks, chunk_results, strict=True):
        mentions = extractor.extract(chunk.content, document.language)
        if not mentions:
            continue
        entity_ids = await self.repository.upsert_entities(mentions)
        triples = [
            (entity_ids[(m.entity_type, m.normalized_name)], chunk.id, m.extraction_method)
            for m in mentions
        ]
        await self.repository.record_mentions(chunk.id, triples)
```

**Search path (in `search()` after temporal boost at ~L707, before sort at L709):**
```python
if settings.entity_boost_enabled and settings.entity_extraction_enabled:
    try:
        extractor = await get_entity_extractor()
        query_entities = extractor.extract(request.query[:500], request.language or "lv")
        if query_entities:
            query_entity_ids = await self.repository.get_entity_ids_for_names(
                [(e.entity_type, e.normalized_name) for e in query_entities]
            )
            if query_entity_ids:
                chunk_entity_map = await self.repository.get_entity_ids_for_chunks(list(chunk_scores.keys()))
                boost = settings.entity_boost_multiplier
                for cid in chunk_scores:
                    shared = chunk_entity_map.get(cid, frozenset()) & query_entity_ids
                    if shared:
                        chunk_scores[cid] *= boost
                        logger.debug("knowledge.search.entity_boost_applied",
                                     chunk_id=cid, matches=len(shared), multiplier=boost)
    except Exception as e:
        # Fail-open: log but do not block search
        logger.warning("knowledge.search.entity_boost_failed", error=str(e))
```

Also populate `SearchResult.entities` by joining entity names onto each returned chunk (single bulk query after final top-K is selected).

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check app/knowledge/service.py && uv run pyright app/knowledge/service.py && uv run mypy app/knowledge/service.py`

### 9. Config — update `app/core/config.py`

Add to `Settings` class, adjacent to existing `rrf_*` / `temporal_boost_*` flags (around L260):
```python
entity_extraction_enabled: bool = True
entity_boost_enabled: bool = True
entity_boost_multiplier: float = Field(default=1.3, ge=1.0, le=3.0)
entity_mention_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
entity_extractor_provider: Literal["regex", "spacy"] = "regex"
```

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check app/core/config.py && uv run pyright app/core/config.py && uv run mypy app/core/config.py`

### 10. Startup warm-up — update `app/knowledge/lifecycle.py` (or equivalent startup module)

Add to existing warm-up sequence:
```python
from app.knowledge.entity_extractor import get_entity_extractor
from app.knowledge.entities_gazetteer import load_stop_gazetteer

# In startup hook, after embedding provider warm-up
await load_stop_gazetteer()
await get_entity_extractor()  # triggers warm_up() via factory
```

If `lifecycle.py` doesn't own the warm-up chain, add to `app/main.py` lifespan or the existing `warm_up_knowledge_providers()` function — match the existing pattern; do not create a new entry point.

**Validation:** `uv run ruff format app/knowledge/lifecycle.py && uv run ruff check app/knowledge/lifecycle.py && uv run pyright app/knowledge/lifecycle.py && uv run mypy app/knowledge/lifecycle.py`

(Note: `lifecycle.py` is a KB-4 WIP file. Make MINIMAL edits — only add the two imports + calls in the established warm-up sequence; do not touch KB-4 code. If the file has import errors unrelated to KB-5, leave them alone.)

### 11. Pyproject — update `pyproject.toml`

```toml
[dependency-groups]
ner = [
    "spacy>=3.7,<4.0",
]

[[tool.mypy.overrides]]
module = ["spacy", "spacy.*"]
ignore_missing_imports = true
```

Do NOT install the `ner` group in CI by default — it's optional. Dev instructions: `uv sync --group ner` for anyone who wants spaCy active.

**Validation:** `uv run ruff check . && uv run mypy app/knowledge/entity_extractor.py` (confirms spaCy is allowed missing).

### 12. Tests — CREATE `app/knowledge/tests/test_entity_extractor.py`

Unit tests, no DB, no integration marker. Target: 12+ tests.

```python
class TestRegexExtractor:
    def test_route_latvian() -> None:
        # "Maršruts 22 aiziet no Brīvības iela" → entity route_22
    def test_route_english() -> None:
        # "Route 22 departs from Central Station" → entity route_22
    def test_route_multiple_mentions_dedupe() -> None:
        # Same route mentioned 3x → single ExtractedEntity, mention_count=3
    def test_stop_name_from_gazetteer() -> None:
        # Pre-seed _stop_names_lower with {"brīvības iela"}; text contains it → extracted
    def test_stop_case_insensitive() -> None:
        # Text has "BRĪVĪBAS IELA", gazetteer has "brīvības iela"
    def test_regulation_eu() -> None:
        # "EU 561/2006" → regulation_561/2006
    def test_normalization_idempotent() -> None:
        # normalize_route called twice returns same
    def test_empty_text_returns_empty_list() -> None:
    def test_oversized_text_is_bounded() -> None:
        # 50k-char input doesn't hang; text clipped to 20000
    def test_no_entities_found() -> None:

class TestSpacyExtractorFallback:
    async def test_spacy_missing_returns_empty() -> None:
        # Monkeypatch spacy.load to raise ImportError; extractor.extract returns []
    async def test_spacy_loaded_extracts_person() -> None:
        # Inject fake _nlp MagicMock returning an ent with label_="PERSON"

class TestFactory:
    async def test_factory_returns_noop_when_disabled() -> None:
        # settings.entity_extraction_enabled=False → NoopEntityExtractor
    async def test_factory_returns_regex_when_provider_regex() -> None:
```

**Validation:** `uv run pytest app/knowledge/tests/test_entity_extractor.py -v`

### 13. Tests — CREATE `app/knowledge/tests/test_entity_boost.py`

Integration-level boost tests. Target: 6+ tests, use `@pytest.mark.integration`.

```python
@pytest.mark.integration
class TestEntityBoost:
    async def test_boost_applied_when_query_and_chunk_share_entity() -> None:
        # Seed: 2 chunks, chunk A mentions route_22, chunk B mentions route_33
        # Query "Route 22 delays" → chunk A score > chunk B after boost
    async def test_boost_multiplier_from_config() -> None:
        # Set multiplier=2.0 in mock_settings; verify score exactly 2x pre-boost
    async def test_no_entity_in_query_no_boost() -> None:
        # Query "transit delays" (no entity) → scores unchanged
    async def test_boost_disabled_flag_bypasses_logic() -> None:
        # entity_boost_enabled=False → no repository calls for entity lookup
    async def test_boost_fails_open_on_extractor_error() -> None:
        # Monkeypatch extractor.extract to raise; search still returns non-empty
    async def test_search_result_entities_populated() -> None:
        # Returned SearchResult.entities contains the matched entity names
```

**Validation:** `uv run pytest app/knowledge/tests/test_entity_boost.py -v` (requires Docker / DB).

## Verification

- [ ] `uv run alembic upgrade head` applies cleanly; `alembic downgrade -1` + re-upgrade succeeds
- [ ] `make lint` — ruff format + check passes
- [ ] `uv run pyright app/knowledge/repository.py app/knowledge/chunking.py app/knowledge/entity_extractor.py app/knowledge/entities_gazetteer.py` — **0 errors** in these files (KB-5's scope)
- [ ] `uv run mypy app/knowledge/repository.py app/knowledge/chunking.py app/knowledge/entity_extractor.py app/knowledge/entities_gazetteer.py` — **0 errors** in these files
- [ ] `uv run pytest app/knowledge/tests/test_entity_extractor.py app/knowledge/tests/test_entity_boost.py -v` — all new tests pass
- [ ] `make test` — no regressions in other knowledge tests (feedback / versioning / repository / service)
- [ ] Pyright full-module baseline does not increase: still ≤ 60 errors across `app/knowledge/` (60 was baseline; boundary-crossing edits to `service.py` / `repository.py` / `chunking.py` / `models.py` / `schemas.py` must stay at 0 new errors)
- [ ] `make security-audit-quick` passes
- [ ] Manual smoke: upload a document mentioning "Maršruts 22" and "Brīvības iela", search "Route 22 delays"; confirm entity-boosted chunk ranks first; query DB `SELECT * FROM entities; SELECT * FROM entity_mentions;` shows stored extractions
- [ ] Disable flag: `entity_boost_enabled=False` in settings → search ranking reverts to pure RRF + temporal boost
- [ ] spaCy fallback: without `uv sync --group ner` installed, extractor still works (RegexEntityExtractor); no startup crash

## Security Checklist

- [ ] CTX-INPUT: all regex patterns bounded; input clipped to 20k chars before extraction; query clipped to 500 chars; `Entity.name` + `EntityMention.mention_text` have `max_length` on DB columns and Pydantic schemas
- [ ] CTX-INFRA: spaCy added as optional dep group, not default; fallback path tested; no hardcoded model path outside config
- [ ] No new endpoints added — no new auth / rate-limiting requirements
- [ ] No user-controlled entity names passed to SQL LIKE — repository uses exact-match `SELECT ... WHERE (entity_type, normalized_name) IN (...)`, parameterized
- [ ] Logging: extractor failures logged at `warning` (fail-open), ingestion errors at `error`; no raw text logged (only entity counts + types)
- [ ] Memory: stop gazetteer is bounded by real Riga stop count (~2000 entries, ~50 KB); safe to hold as a module frozenset
