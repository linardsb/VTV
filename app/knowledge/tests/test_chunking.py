"""Tests for recursive text chunking."""

from app.knowledge.chunking import ChunkResult, chunk_text


def test_short_text_single_chunk():
    """Short text should produce a single chunk."""
    result = chunk_text("Hello world", chunk_size=512)
    assert len(result) == 1
    assert result[0].content == "Hello world"
    assert result[0].chunk_index == 0


def test_empty_text_no_chunks():
    """Empty or whitespace text should produce no chunks."""
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_paragraph_splitting():
    """Text with paragraphs should split on paragraph boundaries."""
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = chunk_text(text, chunk_size=30, chunk_overlap=5)
    assert len(result) >= 2
    for chunk in result:
        assert isinstance(chunk, ChunkResult)
        assert chunk.content.strip()


def test_overlap_between_chunks():
    """Consecutive chunks should have overlapping content when overlap > 0."""
    words = " ".join(f"word{i}" for i in range(100))
    result = chunk_text(words, chunk_size=50, chunk_overlap=10)
    assert len(result) >= 2
    # All chunks should have content
    for chunk in result:
        assert len(chunk.content) > 0


def test_latvian_diacritics_preserved(sample_latvian_text: str) -> None:
    """Latvian diacritics should be preserved in chunks."""
    result = chunk_text(sample_latvian_text, chunk_size=100, chunk_overlap=10)
    assert len(result) >= 2
    # Check that Latvian words appear in chunks
    all_text = " ".join(c.content for c in result)
    assert "Rigas" in all_text
    assert "Satiksme" in all_text


def test_metadata_char_offsets():
    """Chunks should include char_start and char_end metadata."""
    text = "First section.\n\nSecond section.\n\nThird section."
    result = chunk_text(text, chunk_size=30, chunk_overlap=5)
    for chunk in result:
        assert "char_start" in chunk.metadata
        assert "char_end" in chunk.metadata
        start = chunk.metadata["char_start"]
        end = chunk.metadata["char_end"]
        assert isinstance(start, int)
        assert isinstance(end, int)
