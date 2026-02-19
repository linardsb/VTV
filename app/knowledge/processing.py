# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Document text extraction for PDFs, Word, email, images, plain text.

All extraction functions are synchronous and called via asyncio.to_thread()
to avoid blocking the event loop during CPU-bound operations.
"""

from __future__ import annotations

import asyncio
import email as email_lib
from collections.abc import Callable
from pathlib import Path

from app.core.logging import get_logger
from app.knowledge.exceptions import UnsupportedDocumentTypeError

logger = get_logger(__name__)


async def extract_text(file_path: str, source_type: str) -> str:
    """Extract text from a document file.

    Routes to the appropriate extractor based on source_type.
    All extractors run in a thread pool to keep the event loop responsive.

    Args:
        file_path: Absolute path to the file on disk.
        source_type: One of pdf, docx, email, image, text.

    Returns:
        Extracted text content.

    Raises:
        UnsupportedDocumentTypeError: If source_type is not recognized.
    """
    logger.info("knowledge.extraction.started", source_type=source_type, file_path=file_path)

    extractors: dict[str, Callable[[str], str]] = {
        "pdf": _extract_pdf_sync,
        "docx": _extract_docx_sync,
        "email": _extract_email_sync,
        "image": _extract_image_sync,
        "text": _extract_text_sync,
    }

    extractor = extractors.get(source_type)
    if extractor is None:
        raise UnsupportedDocumentTypeError(f"Unsupported document type: {source_type}")

    text: str = await asyncio.to_thread(extractor, file_path)

    logger.info(
        "knowledge.extraction.completed",
        source_type=source_type,
        char_count=len(text),
    )
    return text


def _extract_pdf_sync(file_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Concatenated text from all pages.
    """
    import fitz

    doc = fitz.open(file_path)
    pages: list[str] = []
    for page in doc:
        raw = page.get_text()
        page_text = str(raw) if raw else ""
        if page_text.strip():
            pages.append(page_text)
    doc.close()
    return "\n\n".join(pages)


def _extract_docx_sync(file_path: str) -> str:
    """Extract text from a Word document using python-docx.

    Args:
        file_path: Path to the .docx file.

    Returns:
        Concatenated paragraph text.
    """
    from docx import Document as DocxDocument

    doc = DocxDocument(file_path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_email_sync(file_path: str) -> str:
    """Extract text from an email file (.eml).

    Args:
        file_path: Path to the email file.

    Returns:
        Email headers and body text.
    """
    with Path(file_path).open() as f:
        msg = email_lib.message_from_file(f)

    parts: list[str] = []

    # Extract headers
    for header in ("From", "To", "Date", "Subject"):
        value = msg.get(header)
        if value:
            parts.append(f"{header}: {value}")

    # Extract body
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    parts.append(payload.decode("utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            parts.append(payload.decode("utf-8", errors="replace"))

    return "\n\n".join(parts)


def _extract_image_sync(file_path: str) -> str:
    """Extract text from an image using OCR (Tesseract).

    Uses Latvian + English language packs for multilingual support.

    Args:
        file_path: Path to the image file.

    Returns:
        OCR-extracted text.
    """
    import pytesseract
    from PIL import Image

    image = Image.open(file_path)
    raw = pytesseract.image_to_string(image, lang="lav+eng")
    return str(raw)


def _extract_text_sync(file_path: str) -> str:
    """Read a plain text file.

    Args:
        file_path: Path to the text file.

    Returns:
        File content as string.
    """
    return Path(file_path).read_text(encoding="utf-8")
