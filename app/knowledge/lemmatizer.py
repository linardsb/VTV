# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportMissingImports=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false
"""Latvian UDPipe lemmatization for BM25 fulltext search (KB-2).

Latvian nouns have 7 cases and verbs 6 conjugations, so unstemmed BM25
(``to_tsvector('simple', ...)``) never matches inflected forms such as
``autobuss`` / ``autobusam`` / ``autobusu``. Lemmatizing both the indexed
chunks and the query collapses these into a shared form.

Provider is selected via ``latvian_lemmatizer_enabled``. When disabled
or the UDPipe model file is missing, :class:`NoopLemmatizer` is used and
search degrades gracefully to raw-text BM25.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class LemmaTokenizer(Protocol):
    """Protocol for lemmatizer providers."""

    async def warm_up(self) -> None:
        """Pre-load any heavy model so the first search has no cold start."""
        ...

    def lemmatize(self, text: str, language: str) -> str:
        """Return the lemmatized form of ``text`` or the original on passthrough."""
        ...


class UDPipeLemmatizer:
    """Latvian lemmatizer backed by a pre-trained UDPipe model.

    Model loading is lazy and offloaded to a worker thread; the first
    call to :meth:`lemmatize` (or an explicit :meth:`warm_up`) triggers
    the I/O. ``lemmatize`` itself is synchronous — UDPipe releases the
    GIL during tokenize/tag/lemmatize so the cost in-thread is low,
    but callers processing many documents should offload batches to
    ``asyncio.to_thread`` to avoid starving the event loop.
    """

    def __init__(self, model_path: str) -> None:
        """Initialize with a filesystem path to the UDPipe model.

        Args:
            model_path: Absolute or CWD-relative path to the ``.udpipe``
                model file. Never user-controlled (CTX-INFRA).
        """
        self._model_path = model_path
        self._model: Any | None = None
        self._pipeline: Any | None = None

    async def warm_up(self) -> None:
        """Pre-load the UDPipe model so the first search has no cold start."""
        if self._pipeline is not None:
            return
        start = time.monotonic()
        logger.info("knowledge.lemmatizer.warming_up", path=self._model_path)
        await asyncio.to_thread(self._load)
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.lemmatizer.loaded",
            path=self._model_path,
            duration_ms=duration_ms,
        )

    def _load(self) -> None:
        """Load the UDPipe model and build a tokenize-tag-lemmatize pipeline."""
        from ufal.udpipe import Model, Pipeline

        path = Path(self._model_path)
        if not path.exists():
            logger.error(
                "knowledge.lemmatizer.failed",
                reason="model_missing",
                path=str(path),
            )
            raise FileNotFoundError(f"UDPipe model not found: {path}")

        model = Model.load(str(path))
        if model is None:
            logger.error(
                "knowledge.lemmatizer.failed",
                reason="load_returned_none",
                path=str(path),
            )
            raise RuntimeError(f"UDPipe Model.load returned None for {path}")

        self._model = model
        self._pipeline = Pipeline(
            model,
            "tokenize",
            Pipeline.DEFAULT,
            Pipeline.DEFAULT,
            "conllu",
        )

    def lemmatize(self, text: str, language: str) -> str:
        """Lemmatize ``text`` when ``language == "lv"``, passthrough otherwise.

        Args:
            text: Raw text to lemmatize.
            language: ISO-ish language code. Only ``"lv"`` triggers lemmatization.

        Returns:
            Space-joined lower-cased lemmas, or the original text unchanged
            when ``language != "lv"`` or ``text`` is empty.
        """
        if language != "lv" or not text:
            return text
        if self._pipeline is None:
            self._load()
        if self._pipeline is None:
            raise RuntimeError("UDPipe pipeline not initialized after _load()")
        processed = self._pipeline.process(text)
        if not isinstance(processed, str):
            processed = str(processed)
        return _extract_lemmas(processed)


def _extract_lemmas(conllu: str) -> str:
    """Parse CoNLL-U output and return space-joined lower-cased lemmas.

    CoNLL-U format: TAB-separated columns per token, one token per line.
    Column 3 (0-indexed 2) is LEMMA. Comment and blank lines separate
    sentences and are skipped.

    Args:
        conllu: Raw CoNLL-U text produced by UDPipe.

    Returns:
        Lower-cased lemmas joined by single spaces. Empty string if no
        tokens are present.
    """
    lemmas: list[str] = []
    for line in conllu.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 3:
            lemma = fields[2].strip()
            if lemma and lemma != "_":
                lemmas.append(lemma.lower())
    return " ".join(lemmas)


class NoopLemmatizer:
    """Passthrough lemmatizer used when the feature is disabled."""

    async def warm_up(self) -> None:
        """No-op warm up — logs the skip once."""
        logger.info("knowledge.lemmatizer.skipped", reason="disabled_in_config")

    def lemmatize(self, text: str, language: str) -> str:
        """Return ``text`` unchanged.

        Args:
            text: Raw text (returned as-is).
            language: Unused.
        """
        _ = language
        return text


def get_lemmatizer_provider(settings: Settings) -> LemmaTokenizer:
    """Create a lemmatizer provider based on application settings.

    Args:
        settings: Application settings with lemmatizer configuration.

    Returns:
        :class:`UDPipeLemmatizer` when enabled, :class:`NoopLemmatizer` otherwise.
    """
    if not settings.latvian_lemmatizer_enabled:
        return NoopLemmatizer()
    return UDPipeLemmatizer(model_path=settings.udpipe_model_path)
