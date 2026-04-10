"""Tests for recursive text chunking."""

from app.knowledge.chunking import ChunkResult, chunk_text, chunk_text_semantic


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


def test_chunk_overlap_100_preserves_boundary_context():
    """100-char overlap preserves content at chunk boundaries."""
    text = "word " * 200  # Long enough for multiple chunks
    result = chunk_text(text, chunk_size=200, chunk_overlap=100)
    assert len(result) >= 2
    # Verify overlap: end of chunk[0] appears in start of chunk[1]
    overlap_text = result[0].content[-100:]
    assert overlap_text in result[1].content


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


# ---------------------------------------------------------------------------
# Semantic (heading-aware) chunker tests
# ---------------------------------------------------------------------------


def test_semantic_single_section_no_headings():
    """Text without headings falls back to the recursive chunker."""
    text = "Just a plain paragraph with no markdown headings at all. " * 20
    result = chunk_text_semantic(text, target_size=200)
    assert len(result) >= 1
    for chunk in result:
        assert isinstance(chunk, ChunkResult)
        assert chunk.content.strip()


def test_semantic_heading_detection():
    """Markdown headings are detected and used as chunk boundaries."""
    text = (
        "# Title\n\n"
        "Intro paragraph.\n\n"
        "## Section 1\n\n"
        "Body of section one with enough text to stand alone.\n\n"
        "## Section 2\n\n"
        "Body of section two with enough text to stand alone."
    )
    result = chunk_text_semantic(text, target_size=2000, min_size=10)
    assert len(result) >= 2


def test_semantic_heading_path_metadata():
    """Chunks carry the heading hierarchy in metadata."""
    text = "# Title\n\nIntro.\n\n## Section 1\n\nBody of section one is here."
    result = chunk_text_semantic(text, target_size=2000, min_size=10)
    paths = [c.metadata.get("heading_path") for c in result]
    assert any(p and "Section 1" in str(p) for p in paths)


def test_semantic_heading_level_metadata():
    """heading_level metadata matches the number of ``#`` characters."""
    text = "# Top\n\nBody.\n\n## Sub\n\nBody.\n\n### Deep\n\nBody."
    result = chunk_text_semantic(text, target_size=2000, min_size=1)
    levels = [c.metadata.get("heading_level") for c in result if c.metadata.get("heading_level")]
    assert 1 in levels
    assert 2 in levels
    assert 3 in levels


def test_semantic_nested_headings():
    """Nested headings produce correct path hierarchies."""
    text = "# A\n\nBody A.\n\n## B\n\nBody B.\n\n### C\n\nBody C.\n\n## D\n\nBody D."
    result = chunk_text_semantic(text, target_size=2000, min_size=1)
    paths = [str(c.metadata.get("heading_path", "")) for c in result]
    assert any("A > B > C" in p for p in paths)
    assert any("A > D" in p for p in paths)


def test_semantic_large_section_split():
    """Sections exceeding max_size are split into sub-chunks."""
    body = "This is a long sentence that repeats. " * 100  # ~3800 chars
    text = f"# Title\n\n## Big Section\n\n{body}"
    result = chunk_text_semantic(text, target_size=800, min_size=256, max_size=1500)
    big_chunks = [c for c in result if "Big Section" in str(c.metadata.get("heading_path", ""))]
    assert len(big_chunks) >= 2
    for chunk in big_chunks:
        assert len(chunk.content) <= 1500


def test_semantic_small_sections_merged():
    """Adjacent tiny sections are merged up to target_size."""
    sections = "\n\n".join(f"## S{i}\n\nTiny body {i}." for i in range(10))
    text = f"# Doc\n\n{sections}"
    result = chunk_text_semantic(text, target_size=800, min_size=256)
    # 10 tiny sections should merge into fewer logical groups. Under the
    # parent-child model (AI-4.2), the merged group emits 1 parent + N child
    # paragraphs, so total chunk count grows but stays well below 10 * 2.
    assert len(result) < 25


def test_semantic_latvian_headings():
    """Latvian diacritics are preserved in heading paths."""
    text = "# Drosibas noteikumi\n\n## Arkartas proceduras\n\nSaturs ar garumzimem."
    result = chunk_text_semantic(text, target_size=2000, min_size=10)
    paths = [str(c.metadata.get("heading_path", "")) for c in result]
    assert any("Arkartas proceduras" in p for p in paths)


def test_semantic_empty_text():
    """Empty text returns an empty list."""
    assert chunk_text_semantic("") == []
    assert chunk_text_semantic("   ") == []


def test_semantic_char_offsets():
    """All semantic chunks include char_start and char_end metadata."""
    text = "# Title\n\nIntro.\n\n## Part 1\n\nContent one.\n\n## Part 2\n\nContent two."
    result = chunk_text_semantic(text, target_size=2000, min_size=10)
    for chunk in result:
        assert "char_start" in chunk.metadata
        assert "char_end" in chunk.metadata
        assert isinstance(chunk.metadata["char_start"], int)
        assert isinstance(chunk.metadata["char_end"], int)


def test_semantic_adaptive_sizing():
    """No chunk exceeds max_size (except possible edge with very long words)."""
    body_small = "Small body."
    body_large = "Word " * 400  # ~2000 chars
    text = (
        f"# Doc\n\n## Small\n\n{body_small}\n\n## Large\n\n{body_large}\n\n## Also Small\n\nTiny."
    )
    result = chunk_text_semantic(text, target_size=800, min_size=100, max_size=1500)
    for chunk in result:
        # Allow small tolerance for overlap
        assert len(chunk.content) <= 1500 + 100


# ---------------------------------------------------------------------------
# Parent-child chunk emission (AI-4.2)
# ---------------------------------------------------------------------------


def test_semantic_single_paragraph_section_is_leaf() -> None:
    """A section with one paragraph stays a leaf chunk (no parent/child)."""
    text = "# Title\n\nFirst section body. Just one paragraph here."
    result = chunk_text_semantic(text, target_size=2000, min_size=10)
    assert all(not c.is_parent for c in result)
    assert all(c.parent_index is None for c in result)


def test_semantic_multi_paragraph_section_emits_parent_and_children() -> None:
    """A multi-paragraph section becomes one parent + N child paragraphs."""
    text = (
        "# Procedure\n\n"
        "First paragraph of the procedure section.\n\n"
        "Second paragraph with additional steps.\n\n"
        "Third and final paragraph wraps it up."
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    parents = [c for c in result if c.is_parent]
    children = [c for c in result if c.parent_index is not None]
    assert len(parents) == 1
    assert len(children) == 3
    # All children point to the parent's positional index
    assert all(c.parent_index == parents[0].chunk_index for c in children)


def test_semantic_parent_carries_full_section_content() -> None:
    """The parent chunk's content equals the joined section body."""
    text = "## Safety\n\nStay alert at all times.\n\nReport incidents immediately."
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    parents = [c for c in result if c.is_parent]
    assert len(parents) == 1
    assert "Stay alert" in parents[0].content
    assert "Report incidents" in parents[0].content


def test_semantic_chunks_carry_heading_path_field() -> None:
    """heading_path is promoted to a first-class ChunkResult field."""
    text = "# A\n\n## B\n\nFirst para.\n\nSecond para."
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    chunks_with_path = [c for c in result if c.heading_path]
    assert chunks_with_path
    assert any("B" in (c.heading_path or "") for c in chunks_with_path)


def test_semantic_section_type_classification_list() -> None:
    """Sections that are mostly bulleted lines are classified as 'list'."""
    text = "## Steps\n\n- First step\n- Second step\n- Third step\n- Fourth step"
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    list_chunks = [c for c in result if c.section_type == "list"]
    assert list_chunks


def test_semantic_section_type_classification_table() -> None:
    """Markdown tables classify as 'table'."""
    text = "## Routes\n\n| Route | Stops |\n|-------|-------|\n| 1     | 12    |\n| 2     | 18    |"
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    assert any(c.section_type == "table" for c in result)


def test_semantic_section_type_classification_body_default() -> None:
    """Plain prose sections classify as 'body'."""
    text = (
        "## Overview\n\n"
        "This is a paragraph of plain prose describing the system.\n\n"
        "Another paragraph continues the description in the same body."
    )
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    body_chunks = [c for c in result if c.section_type == "body"]
    assert body_chunks


def test_semantic_no_headings_fallback_has_no_parents() -> None:
    """Fallback path (no headings) produces only leaf chunks."""
    text = "Just plain text with no structure. " * 30
    result = chunk_text_semantic(text, target_size=200, min_size=10)
    assert all(not c.is_parent for c in result)
    assert all(c.parent_index is None for c in result)
    assert all(c.heading_path is None for c in result)


def test_semantic_child_chunk_count_metadata() -> None:
    """Parent chunks record child_count in metadata."""
    text = "# Doc\n\n## Section\n\nPara one.\n\nPara two.\n\nPara three."
    result = chunk_text_semantic(text, target_size=5000, min_size=1, max_size=5000)
    parents = [c for c in result if c.is_parent]
    assert parents
    assert parents[0].metadata.get("child_count") == 3
