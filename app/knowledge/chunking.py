"""Recursive text chunking with metadata preservation.

Splits text using a hierarchy of separators (paragraphs, lines,
sentences, words) to keep semantic units together when possible.
"""

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
    chunk_overlap: int = 50,
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
