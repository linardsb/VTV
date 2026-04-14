"""Unit tests for the KB-5 entity extractor stack."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.knowledge import entities_gazetteer
from app.knowledge.entity_extractor import (
    CompositeExtractor,
    NoopEntityExtractor,
    RegexEntityExtractor,
    SpacyEntityExtractor,
    get_entity_extractor,
    reset_entity_extractor,
)
from app.knowledge.schemas import ExtractedEntity


@pytest.fixture(autouse=True)
def reset_state() -> Any:
    """Ensure gazetteer + factory singleton are clean for each test."""
    entities_gazetteer.reset_gazetteer()
    reset_entity_extractor()
    yield
    entities_gazetteer.reset_gazetteer()
    reset_entity_extractor()


def _seed_stops(names: set[str]) -> None:
    entities_gazetteer.set_gazetteer(frozenset(n.casefold() for n in names))


class TestRegexExtractor:
    def test_route_latvian(self) -> None:
        extractor = RegexEntityExtractor()
        out = extractor.extract("Maršruts 22 aiziet no centra.", "lv")
        types = {(e.entity_type, e.normalized_name) for e in out}
        assert ("route", "route_22") in types

    def test_route_english(self) -> None:
        extractor = RegexEntityExtractor()
        out = extractor.extract("Route 22 departs from Central Station", "en")
        types = {(e.entity_type, e.normalized_name) for e in out}
        assert ("route", "route_22") in types

    def test_route_multiple_mentions_dedupe_and_count(self) -> None:
        extractor = RegexEntityExtractor()
        text = "Route 22 delayed. Route 22 rerouted. Route 22 resumed."
        out = extractor.extract(text, "en")
        route_hits = [e for e in out if e.entity_type == "route"]
        assert len(route_hits) == 1
        assert route_hits[0].mention_count == 3

    def test_stop_name_from_gazetteer(self) -> None:
        _seed_stops({"Brīvības iela"})
        extractor = RegexEntityExtractor()
        out = extractor.extract("Pagaidām Brīvības iela ir slēgta.", "lv")
        stops = [e for e in out if e.entity_type == "stop"]
        assert stops and stops[0].normalized_name == "brīvības iela"

    def test_stop_case_insensitive(self) -> None:
        _seed_stops({"brīvības iela"})
        extractor = RegexEntityExtractor()
        out = extractor.extract("TEXT WITH BRĪVĪBAS IELA UPPERCASE", "lv")
        assert any(e.entity_type == "stop" for e in out)

    def test_regulation_eu(self) -> None:
        extractor = RegexEntityExtractor()
        out = extractor.extract("Per EU 561/2006 rules…", "en")
        regs = [e for e in out if e.entity_type == "regulation"]
        assert regs and regs[0].normalized_name == "reg_561/2006"

    def test_normalization_idempotent(self) -> None:
        first = entities_gazetteer.normalize_route("Maršruts 22")
        second = entities_gazetteer.normalize_route(f"Route {first.split('_')[-1]}")
        assert first == second == "route_22"

    def test_empty_text_returns_empty_list(self) -> None:
        extractor = RegexEntityExtractor()
        assert extractor.extract("", "lv") == []

    def test_oversized_text_is_bounded(self) -> None:
        huge = "Route 22 " * 10_000
        extractor = RegexEntityExtractor()
        out = extractor.extract(huge, "en")
        # Clipping limits regex scope; still at least one route match.
        assert any(e.entity_type == "route" for e in out)

    def test_no_entities_found(self) -> None:
        extractor = RegexEntityExtractor()
        assert extractor.extract("Plain sentence with no entities.", "en") == []


class TestSpacyExtractorFallback:
    async def test_spacy_missing_returns_empty(self) -> None:
        extractor = SpacyEntityExtractor(model_name="does_not_exist")
        await extractor.warm_up()
        assert extractor.extract("Some text with names.", "en") == []

    async def test_spacy_loaded_extracts_person(self) -> None:
        extractor = SpacyEntityExtractor()
        fake_ent = MagicMock()
        fake_ent.label_ = "PERSON"
        fake_ent.text = "Jānis Bērziņš"
        fake_doc = MagicMock()
        fake_doc.ents = [fake_ent]
        fake_nlp = MagicMock(return_value=fake_doc)
        extractor._nlp = fake_nlp
        out = extractor.extract("Jānis Bērziņš attended.", "lv")
        assert len(out) == 1
        assert out[0].entity_type == "person"
        assert out[0].extraction_method == "spacy"


class TestComposite:
    async def test_composite_dedupes_across_extractors(self) -> None:
        _seed_stops({"Centrs"})
        regex = RegexEntityExtractor()
        spacy = SpacyEntityExtractor()
        # Spawn "loaded" spacy extractor that returns one ORG.
        fake_ent = MagicMock()
        fake_ent.label_ = "ORG"
        fake_ent.text = "Rīgas Satiksme"
        fake_doc = MagicMock()
        fake_doc.ents = [fake_ent]
        spacy._nlp = MagicMock(return_value=fake_doc)

        composite = CompositeExtractor(regex, spacy)
        out = composite.extract("Rīgas Satiksme operates Route 22 via Centrs.", "lv")
        types = {(e.entity_type, e.normalized_name) for e in out}
        assert ("route", "route_22") in types
        assert ("org", "rīgas satiksme") in types


class TestFactory:
    async def test_factory_returns_noop_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core import config as config_module
        from app.knowledge import entity_extractor as ext_module

        original = config_module.get_settings()
        disabled = original.model_copy(update={"entity_extraction_enabled": False})
        monkeypatch.setattr(ext_module, "get_settings", lambda: disabled)
        ext = await get_entity_extractor()
        assert isinstance(ext, NoopEntityExtractor)
        assert ext.extract("Route 22", "en") == []

    async def test_factory_returns_regex_when_provider_regex(self) -> None:
        ext = await get_entity_extractor()
        assert isinstance(ext, RegexEntityExtractor)


class TestExtractedEntityModel:
    def test_max_length_enforced(self) -> None:
        with pytest.raises(ValueError):
            ExtractedEntity(
                entity_type="route",
                name="x" * 1000,
                normalized_name="route_x",
                extraction_method="regex",
                mention_count=1,
            )
