"""Recursive text chunking with metadata preservation.

Splits text using a hierarchy of separators (paragraphs, lines,
sentences, words) to keep semantic units together when possible.
Includes heading-aware semantic chunking for structured documents.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ChunkResult:
    """A single chunk of text with position metadata."""

    content: str
    chunk_index: int
    metadata: dict[str, str | int | None] = field(
        default_factory=lambda: dict[str, str | int | None]()
    )


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 100,
) -> list[ChunkResult]:
    """Split text into overlapping chunks using recursive splitting.

    Tries to split by paragraphs first, then lines, sentences, words.
    Each chunk includes character offset metadata for traceability.

    Args:
        text: The full document text to chunk.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of overlapping characters between chunks.

    Returns:
        List of ChunkResult with content and metadata.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    if len(text) <= chunk_size:
        return [
            ChunkResult(
                content=text,
                chunk_index=0,
                metadata={"char_start": 0, "char_end": len(text)},
            )
        ]

    # Try splitting by different separators
    separators = ["\n\n", "\n", ". ", " "]
    segments = _split_by_separators(text, separators, chunk_size)

    # Build chunks with overlap
    chunks = _build_chunks(segments, chunk_size, chunk_overlap)

    # Assign indices and metadata
    results: list[ChunkResult] = []
    char_pos = 0
    for idx, chunk_text_content in enumerate(chunks):
        # Find the actual position in the original text
        pos = text.find(chunk_text_content[:50], max(0, char_pos - chunk_overlap))
        if pos == -1:
            pos = char_pos
        results.append(
            ChunkResult(
                content=chunk_text_content,
                chunk_index=idx,
                metadata={"char_start": pos, "char_end": pos + len(chunk_text_content)},
            )
        )
        char_pos = pos + len(chunk_text_content) - chunk_overlap

    return results


def _split_by_separators(text: str, separators: list[str], chunk_size: int) -> list[str]:
    """Recursively split text using a hierarchy of separators.

    Args:
        text: Text to split.
        separators: Ordered list of separators to try.
        chunk_size: Maximum chunk size.

    Returns:
        List of text segments, each at most chunk_size characters.
    """
    if len(text) <= chunk_size:
        return [text]

    for sep in separators:
        parts = text.split(sep)
        if len(parts) > 1:
            segments: list[str] = []
            for part in parts:
                stripped = part.strip()
                if not stripped:
                    continue
                if len(stripped) <= chunk_size:
                    segments.append(stripped)
                else:
                    # Recursively split with remaining separators
                    remaining_seps = separators[separators.index(sep) + 1 :]
                    if remaining_seps:
                        segments.extend(_split_by_separators(stripped, remaining_seps, chunk_size))
                    else:
                        # Last resort: hard split by character
                        for i in range(0, len(stripped), chunk_size):
                            segments.append(stripped[i : i + chunk_size])
            return segments

    # No separator worked: hard split
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _build_chunks(segments: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Merge segments into chunks respecting size and overlap constraints.

    Args:
        segments: Text segments from splitting.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Desired overlap between consecutive chunks.

    Returns:
        List of chunk strings.
    """
    if not segments:
        return []

    chunks: list[str] = []
    current = segments[0]

    for segment in segments[1:]:
        combined = current + " " + segment
        if len(combined) <= chunk_size:
            current = combined
        else:
            chunks.append(current)
            # Create overlap from end of previous chunk
            if chunk_overlap > 0 and len(current) > chunk_overlap:
                overlap_text = current[-chunk_overlap:]
                current = overlap_text + " " + segment
                if len(current) > chunk_size:
                    current = segment
            else:
                current = segment

    if current.strip():
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# Heading-aware semantic chunker
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class _Section:
    """Internal representation of a document section under a heading."""

    heading_level: int
    heading_text: str
    heading_path: str
    content: str


def _extract_sections(text: str) -> list[_Section]:
    """Parse markdown headings and split text into sections.

    Each section includes its heading hierarchy as a path string
    (e.g. "Safety > Emergency Procedures").

    Args:
        text: Markdown text with ``#`` headings.

    Returns:
        List of sections preserving document order.
    """
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        return [
            _Section(
                heading_level=0,
                heading_text="",
                heading_path="",
                content=text.strip(),
            )
        ]

    sections: list[_Section] = []
    # Stack tracks the heading hierarchy: list of (level, heading_text) pairs
    heading_stack: list[tuple[int, str]] = []

    # Content before the first heading (preamble)
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(
            _Section(heading_level=0, heading_text="", heading_path="", content=preamble)
        )

    for i, match in enumerate(matches):
        level = len(match.group(1))
        heading_text = match.group(2).strip()

        # Pop stack to parent level
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, heading_text))

        heading_path = " > ".join(h[1] for h in heading_stack)

        # Body is text between this heading and the next (or end)
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()

        sections.append(
            _Section(
                heading_level=level,
                heading_text=heading_text,
                heading_path=heading_path,
                content=body,
            )
        )

    return sections


def _merge_small_sections(
    sections: list[_Section],
    min_size: int,
    target_size: int,
) -> list[_Section]:
    """Merge consecutive small sections up to *target_size*.

    Sections are merged when the combined content length stays under
    *target_size* and the section being merged is smaller than *min_size*.

    Args:
        sections: Ordered sections from ``_extract_sections``.
        min_size: Sections smaller than this are merge candidates.
        target_size: Maximum combined size after merging.

    Returns:
        New list of sections (may be shorter than input).
    """
    if not sections:
        return []

    merged: list[_Section] = [sections[0]]

    for section in sections[1:]:
        prev = merged[-1]
        combined_len = len(prev.content) + len(section.content) + 1  # +1 for join
        if len(section.content) < min_size and combined_len <= target_size:
            merged[-1] = _Section(
                heading_level=prev.heading_level,
                heading_text=prev.heading_text,
                heading_path=prev.heading_path,
                content=prev.content + "\n\n" + section.content,
            )
        else:
            merged.append(section)

    return merged


def _split_large_sections(
    sections: list[_Section],
    max_size: int,
    chunk_overlap: int,
) -> list[_Section]:
    """Split sections whose content exceeds *max_size*.

    Splits first at paragraph boundaries (``\\n\\n``), then at sentence
    boundaries (``. ``). Each sub-section inherits the parent heading path.

    Args:
        sections: Ordered sections (possibly merged).
        max_size: Maximum content length per section.
        chunk_overlap: Overlap characters between sub-chunks.

    Returns:
        New list with large sections replaced by sub-sections.
    """
    result: list[_Section] = []

    for section in sections:
        if len(section.content) <= max_size:
            result.append(section)
            continue

        # Use the existing recursive splitter then rebuild chunks with overlap
        sub_chunks = _build_chunks(
            _split_by_separators(section.content, ["\n\n", ". ", " "], max_size),
            max_size,
            chunk_overlap,
        )

        for sub in sub_chunks:
            result.append(
                _Section(
                    heading_level=section.heading_level,
                    heading_text=section.heading_text,
                    heading_path=section.heading_path,
                    content=sub,
                )
            )

    return result


def chunk_text_semantic(
    text: str,
    target_size: int = 800,
    min_size: int = 256,
    max_size: int = 1500,
    chunk_overlap: int = 100,
) -> list[ChunkResult]:
    """Split text into chunks using heading-aware semantic boundaries.

    Parses markdown ``#`` headings to identify document structure, then
    produces chunks that respect section boundaries. Falls back to the
    fixed-size recursive chunker when no headings are detected.

    Args:
        text: The full document text (markdown with headings).
        target_size: Preferred chunk size in characters.
        min_size: Sections smaller than this may be merged with neighbours.
        max_size: Sections larger than this are split at paragraph/sentence
            boundaries.
        chunk_overlap: Overlap characters when splitting large sections.

    Returns:
        List of ``ChunkResult`` with ``heading_path``, ``heading_level``,
        ``char_start``, and ``char_end`` in metadata.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    sections = _extract_sections(text)

    # Fallback: if no real headings found (only a single preamble section),
    # delegate to the fixed-size recursive chunker
    if len(sections) < 2 and sections[0].heading_level == 0:
        return chunk_text(text, chunk_size=target_size, chunk_overlap=chunk_overlap)

    sections = _merge_small_sections(sections, min_size, target_size)
    sections = _split_large_sections(sections, max_size, chunk_overlap)

    results: list[ChunkResult] = []
    for idx, section in enumerate(sections):
        content = section.content
        if not content.strip():
            continue

        # Compute character offsets in original text
        char_start = text.find(content[:80]) if len(content) >= 80 else text.find(content)
        if char_start == -1:
            char_start = 0
        char_end = char_start + len(content)

        metadata: dict[str, str | int | None] = {
            "heading_path": section.heading_path if section.heading_path else None,
            "heading_level": section.heading_level if section.heading_level > 0 else None,
            "char_start": char_start,
            "char_end": char_end,
        }

        results.append(ChunkResult(content=content, chunk_index=idx, metadata=metadata))

    return results
