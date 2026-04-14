# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingImports=false, reportAttributeAccessIssue=false
"""Entity extractor for KB-5 knowledge-graph overlay.

Three providers compose behind the :class:`EntityExtractor` protocol:

* :class:`RegexEntityExtractor` — always-available regex + gazetteer, extracts
  route numbers, EU/ES regulations, and any stop name present in the loaded
  GTFS gazetteer. Deterministic and cheap.
* :class:`SpacyEntityExtractor` — optional, adds PERSON/ORG via spaCy NER
  when the ``ner`` dependency group is installed. Falls back silently when
  spaCy or the configured model is missing.
* :class:`NoopEntityExtractor` — returned when
  ``settings.entity_extraction_enabled`` is ``False`` so downstream code
  paths can unconditionally call ``extract()``.

The factory :func:`get_entity_extractor` caches a singleton per process,
warmed up once at startup.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from app.core.config import get_settings
from app.core.logging import get_logger
from app.knowledge.entities_gazetteer import (
    _REGULATION_RE,
    _ROUTE_RE,
    MAX_INPUT_CHARS,
    get_stop_names,
    load_stop_gazetteer,
    normalize_regulation,
    normalize_route,
    normalize_stop,
)
from app.knowledge.schemas import ExtractedEntity

logger = get_logger(__name__)


@runtime_checkable
class EntityExtractor(Protocol):
    """Protocol for KB-5 entity extractors."""

    async def warm_up(self) -> None:
        """Pre-load any heavy models / gazetteers so first call is fast."""
        ...

    def extract(self, text: str, language: str) -> list[ExtractedEntity]:
        """Extract entities from ``text``.

        Args:
            text: Raw source text. Implementations must clip it to
                :data:`MAX_INPUT_CHARS` before regex evaluation to bound
                worst-case CPU (CTX-INPUT / ReDoS defence).
            language: Document language code (``"lv"`` / ``"en"``). Not
                all extractors use this; kept in the protocol so future
                language-specific logic can hook in without widening.

        Returns:
            Deduplicated list keyed on ``(entity_type, normalized_name)``.
            Returns an empty list for empty input.
        """
        ...


def _extract_regex_hits(text: str) -> dict[tuple[str, str], ExtractedEntity]:
    """Find route + regulation matches in ``text`` (regex, always-on)."""
    found: dict[tuple[str, str], ExtractedEntity] = {}
    for match in _ROUTE_RE.finditer(text):
        raw = match.group(0)
        norm = normalize_route(raw)
        key = ("route", norm)
        existing = found.get(key)
        count = existing.mention_count + 1 if existing else 1
        found[key] = ExtractedEntity(
            entity_type="route",
            name=raw,
            normalized_name=norm,
            extraction_method="regex",
            mention_count=count,
        )
    for match in _REGULATION_RE.finditer(text):
        raw = match.group(0)
        norm = normalize_regulation(raw)
        key = ("regulation", norm)
        existing = found.get(key)
        count = existing.mention_count + 1 if existing else 1
        found[key] = ExtractedEntity(
            entity_type="regulation",
            name=raw,
            normalized_name=norm,
            extraction_method="regex",
            mention_count=count,
        )
    return found


def _extract_gazetteer_hits(text: str) -> dict[tuple[str, str], ExtractedEntity]:
    """Find GTFS stop-name mentions via the loaded gazetteer."""
    stops = get_stop_names()
    if not stops:
        return {}
    folded = text.casefold()
    found: dict[tuple[str, str], ExtractedEntity] = {}
    for stop_name in stops:
        if not stop_name:
            continue
        if stop_name in folded:
            norm = normalize_stop(stop_name)
            key = ("stop", norm)
            if key in found:
                continue
            found[key] = ExtractedEntity(
                entity_type="stop",
                name=stop_name,
                normalized_name=norm,
                extraction_method="gazetteer",
                mention_count=1,
            )
    return found


class RegexEntityExtractor:
    """Regex + GTFS-gazetteer extractor. Always available, no heavy deps."""

    async def warm_up(self) -> None:
        """Load the GTFS stop gazetteer into memory."""
        await load_stop_gazetteer()

    def extract(self, text: str, language: str) -> list[ExtractedEntity]:
        """Extract routes, regulations, and gazetteer stops from ``text``."""
        _ = language
        if not text:
            return []
        clipped = text[:MAX_INPUT_CHARS]
        found = _extract_regex_hits(clipped)
        for key, value in _extract_gazetteer_hits(clipped).items():
            if key not in found:
                found[key] = value
        return list(found.values())


class SpacyEntityExtractor:
    """Optional spaCy-based PERSON/ORG extractor.

    When spaCy is not installed or the model cannot be loaded, ``_nlp``
    stays ``None`` and :meth:`extract` returns an empty list so callers
    can compose it with the always-on regex extractor without branching.
    """

    def __init__(self, model_name: str = "xx_sent_ud_sm") -> None:
        self._model_name = model_name
        self._nlp: Any | None = None

    async def warm_up(self) -> None:
        """Load the spaCy model in a worker thread; log and skip on failure."""
        try:
            import spacy

            self._nlp = await asyncio.to_thread(spacy.load, self._model_name)
            logger.info(
                "knowledge.entity_extractor.spacy_loaded",
                model=self._model_name,
            )
        except Exception as exc:
            logger.warning(
                "knowledge.entity_extractor.spacy_unavailable",
                reason=str(exc),
                error_type=type(exc).__name__,
            )
            self._nlp = None

    def extract(self, text: str, language: str) -> list[ExtractedEntity]:
        """Run spaCy NER, emitting PERSON/ORG entities only."""
        _ = language
        if self._nlp is None or not text:
            return []
        clipped = text[:MAX_INPUT_CHARS]
        doc = self._nlp(clipped)
        out: dict[tuple[str, str], ExtractedEntity] = {}
        for ent in doc.ents:
            label = str(ent.label_)
            if label not in {"PERSON", "ORG"}:
                continue
            ent_type = "person" if label == "PERSON" else "org"
            raw = str(ent.text)
            norm = raw.casefold().strip()
            if not norm:
                continue
            key = (ent_type, norm)
            existing = out.get(key)
            count = existing.mention_count + 1 if existing else 1
            out[key] = ExtractedEntity(
                entity_type=ent_type,
                name=raw,
                normalized_name=norm,
                extraction_method="spacy",
                mention_count=count,
            )
        return list(out.values())


class CompositeExtractor:
    """Runs regex + spaCy in order, dedupes, preserves mention counts."""

    def __init__(self, regex: RegexEntityExtractor, spacy: SpacyEntityExtractor) -> None:
        self._regex = regex
        self._spacy = spacy

    async def warm_up(self) -> None:
        """Warm both underlying extractors."""
        await self._regex.warm_up()
        await self._spacy.warm_up()

    def extract(self, text: str, language: str) -> list[ExtractedEntity]:
        """Concatenate and dedupe results from both extractors."""
        found: dict[tuple[str, str], ExtractedEntity] = {}
        for entity in self._regex.extract(text, language):
            found[(entity.entity_type, entity.normalized_name)] = entity
        for entity in self._spacy.extract(text, language):
            key = (entity.entity_type, entity.normalized_name)
            if key not in found:
                found[key] = entity
        return list(found.values())


class NoopEntityExtractor:
    """Returned when ``entity_extraction_enabled`` is ``False``."""

    async def warm_up(self) -> None:
        """No-op."""
        return

    def extract(self, text: str, language: str) -> list[ExtractedEntity]:
        """Always return an empty list."""
        _ = text, language
        return []


_extractor_provider: EntityExtractor | None = None


async def get_entity_extractor() -> EntityExtractor:
    """Return the process-wide singleton extractor.

    Creates + warms the configured extractor on first call. Downstream
    callers use the returned instance for all subsequent extractions.
    """
    global _extractor_provider
    if _extractor_provider is not None:
        return _extractor_provider

    settings = get_settings()
    if not settings.entity_extraction_enabled:
        provider: EntityExtractor = NoopEntityExtractor()
        await provider.warm_up()
        _extractor_provider = provider
        return _extractor_provider

    regex = RegexEntityExtractor()
    await regex.warm_up()
    if settings.entity_extractor_provider == "spacy":
        spacy_ext = SpacyEntityExtractor()
        await spacy_ext.warm_up()
        _extractor_provider = CompositeExtractor(regex, spacy_ext)
    else:
        _extractor_provider = regex
    logger.info(
        "knowledge.entity_extractor.ready",
        provider=settings.entity_extractor_provider,
    )
    return _extractor_provider


def reset_entity_extractor() -> None:
    """Drop the cached singleton — test-only helper."""
    global _extractor_provider
    _extractor_provider = None
