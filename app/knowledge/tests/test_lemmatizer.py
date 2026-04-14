# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Unit tests for Latvian UDPipe lemmatizer (KB-2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.knowledge.lemmatizer import (
    NoopLemmatizer,
    UDPipeLemmatizer,
    _extract_lemmas,
    get_lemmatizer_provider,
)

# --- NoopLemmatizer ---


def test_noop_lemmatizer_returns_text_unchanged() -> None:
    """NoopLemmatizer passes text through untouched regardless of language."""
    provider = NoopLemmatizer()
    assert provider.lemmatize("autobusu apkope", "lv") == "autobusu apkope"
    assert provider.lemmatize("hello world", "en") == "hello world"
    assert provider.lemmatize("", "lv") == ""


@pytest.mark.asyncio
async def test_noop_warm_up_completes_without_error() -> None:
    """NoopLemmatizer warm_up is a no-op and must not raise."""
    provider = NoopLemmatizer()
    await provider.warm_up()


# --- UDPipeLemmatizer — passthrough branches ---


def test_udpipe_non_latvian_passthrough() -> None:
    """lemmatize() short-circuits for non-Latvian without loading the model."""
    provider = UDPipeLemmatizer(model_path="/nonexistent.udpipe")
    # Must NOT raise even though the model file is absent.
    assert provider.lemmatize("hello world", "en") == "hello world"
    assert provider._pipeline is None


def test_udpipe_empty_text_passthrough() -> None:
    """Empty text is returned as-is without invoking the model."""
    provider = UDPipeLemmatizer(model_path="/nonexistent.udpipe")
    assert provider.lemmatize("", "lv") == ""
    assert provider._pipeline is None


# --- UDPipeLemmatizer — load failure paths ---


def test_udpipe_warm_up_missing_model_raises() -> None:
    """warm_up surfaces FileNotFoundError when the model file is absent."""
    provider = UDPipeLemmatizer(model_path="/definitely/not/a/real/path.udpipe")
    with pytest.raises(FileNotFoundError, match="UDPipe model not found"):
        provider._load()


# --- UDPipeLemmatizer — lemmatization via fake pipeline ---


def _install_fake_pipeline(provider: UDPipeLemmatizer, conllu_output: str) -> MagicMock:
    """Install a mock pipeline returning canned CoNLL-U so `_load` is skipped."""
    fake_pipeline = MagicMock()
    fake_pipeline.process.return_value = conllu_output
    provider._pipeline = fake_pipeline
    provider._model = MagicMock()
    return fake_pipeline


def test_udpipe_lemmatize_noun_case_collapsed() -> None:
    """Inflected Latvian nouns are collapsed to the canonical lemma."""
    provider = UDPipeLemmatizer(model_path="unused")
    # UDPipe-style CoNLL-U: ID FORM LEMMA UPOS ...
    conllu = (
        "# sent_id = 1\n# text = autobusam\n1\tautobusam\tautobuss\tNOUN\t_\t_\t0\troot\t_\t_\n"
    )
    _install_fake_pipeline(provider, conllu)

    result = provider.lemmatize("autobusam", "lv")
    assert result == "autobuss"


def test_udpipe_lemmatize_multi_token_sentence() -> None:
    """Multi-token Latvian input returns space-joined lemmas."""
    provider = UDPipeLemmatizer(model_path="unused")
    conllu = (
        "# sent_id = 1\n"
        "1\tautobusu\tautobuss\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tapkope\tapkope\tNOUN\t_\t_\t1\tobj\t_\t_\n"
    )
    _install_fake_pipeline(provider, conllu)

    result = provider.lemmatize("autobusu apkope", "lv")
    assert result == "autobuss apkope"


def test_udpipe_lemmatize_lowercases_lemmas() -> None:
    """Capitalised input lemmas are lower-cased for tsvector stability."""
    provider = UDPipeLemmatizer(model_path="unused")
    conllu = "1\tRīga\tRīga\tPROPN\t_\t_\t0\troot\t_\t_\n"
    _install_fake_pipeline(provider, conllu)

    result = provider.lemmatize("Rīga", "lv")
    assert result == "rīga"


def test_udpipe_lemmatize_without_warmup_auto_loads() -> None:
    """First lemmatize() call invokes _load when the pipeline is not set."""
    provider = UDPipeLemmatizer(model_path="unused")

    def fake_load() -> None:
        _install_fake_pipeline(
            provider,
            "1\tautobuss\tautobuss\tNOUN\t_\t_\t0\troot\t_\t_\n",
        )

    with patch.object(provider, "_load", side_effect=fake_load) as load_mock:
        result = provider.lemmatize("autobuss", "lv")

    assert result == "autobuss"
    load_mock.assert_called_once()


# --- _extract_lemmas — pure unit ---


def test_extract_lemmas_parses_conllu_columns() -> None:
    """LEMMA column (index 2) is extracted and joined by spaces."""
    conllu = (
        "# sent_id = 1\n"
        "1\tautobusam\tautobuss\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tbraukt\tbraukt\tVERB\t_\t_\t1\tcc\t_\t_\n"
    )
    assert _extract_lemmas(conllu) == "autobuss braukt"


def test_extract_lemmas_skips_comments_and_blanks() -> None:
    """Comment (# ...) and blank lines are skipped."""
    conllu = (
        "# sent_id = 1\n"
        "\n"
        "1\ta\ta\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "\n"
        "# sent_id = 2\n"
        "1\tb\tb\tNOUN\t_\t_\t0\troot\t_\t_\n"
    )
    assert _extract_lemmas(conllu) == "a b"


def test_extract_lemmas_skips_underscore_lemma() -> None:
    """CoNLL-U uses '_' as a placeholder for missing lemmas — skip them."""
    conllu = "1\tfoo\t_\tNOUN\t_\t_\t0\troot\t_\t_\n2\tbar\tbar\tNOUN\t_\t_\t1\tdep\t_\t_\n"
    assert _extract_lemmas(conllu) == "bar"


def test_extract_lemmas_empty_input() -> None:
    """Empty or comment-only input yields empty string."""
    assert _extract_lemmas("") == ""
    assert _extract_lemmas("# only comment\n# another\n") == ""


# --- warm_up idempotency ---


@pytest.mark.asyncio
async def test_warm_up_idempotent() -> None:
    """Second warm_up does not reload when the pipeline is already set."""
    provider = UDPipeLemmatizer(model_path="unused")
    _install_fake_pipeline(provider, "")
    with patch.object(provider, "_load") as load_mock:
        await provider.warm_up()
    load_mock.assert_not_called()


# --- Factory ---


def test_get_lemmatizer_provider_disabled_returns_noop() -> None:
    """Factory returns NoopLemmatizer when the feature flag is off."""
    settings: Any = MagicMock()
    settings.latvian_lemmatizer_enabled = False
    provider = get_lemmatizer_provider(settings)
    assert isinstance(provider, NoopLemmatizer)


def test_get_lemmatizer_provider_enabled_returns_udpipe() -> None:
    """Factory returns UDPipeLemmatizer when enabled."""
    settings: Any = MagicMock()
    settings.latvian_lemmatizer_enabled = True
    settings.udpipe_model_path = "models/latvian-ud-2.5.udpipe"
    provider = get_lemmatizer_provider(settings)
    assert isinstance(provider, UDPipeLemmatizer)
    assert provider._model_path == "models/latvian-ud-2.5.udpipe"
