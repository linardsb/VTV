# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportOptionalMemberAccess=false
"""Document text extraction for PDFs, Word, email, images, plain text.

All extraction functions are synchronous and called via asyncio.to_thread()
to avoid blocking the event loop during CPU-bound operations.
"""

from __future__ import annotations

import asyncio
import email as email_lib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.knowledge.exceptions import UnsupportedDocumentTypeError

logger = get_logger(__name__)


async def extract_text(file_path: str, source_type: str) -> tuple[str, bool]:
    """Extract text from a document file.

    Routes to the appropriate extractor based on source_type.
    All extractors run in a thread pool to keep the event loop responsive.
    For PDFs, detects scanned pages and falls back to OCR if needed.

    Args:
        file_path: Absolute path to the file on disk.
        source_type: One of pdf, docx, email, image, text.

    Returns:
        Tuple of (extracted text, whether OCR was applied).

    Raises:
        UnsupportedDocumentTypeError: If source_type is not recognized.
    """
    logger.info("knowledge.extraction.started", source_type=source_type, file_path=file_path)

    # PDF is handled separately because it returns a tuple with OCR info
    if source_type == "pdf":
        text, ocr_applied = await asyncio.to_thread(_extract_pdf_sync, file_path)
        logger.info(
            "knowledge.extraction.completed",
            source_type=source_type,
            char_count=len(text),
            ocr_applied=ocr_applied,
        )
        return text, ocr_applied

    extractors: dict[str, Callable[[str], str]] = {
        "docx": _extract_docx_sync,
        "email": _extract_email_sync,
        "image": _extract_image_sync,
        "text": _extract_text_sync,
        "xlsx": _extract_excel_sync,
        "csv": _extract_csv_sync,
    }

    extractor = extractors.get(source_type)
    if extractor is None:
        raise UnsupportedDocumentTypeError(f"Unsupported document type: {source_type}")

    text = await asyncio.to_thread(extractor, file_path)

    logger.info(
        "knowledge.extraction.completed",
        source_type=source_type,
        char_count=len(text),
    )
    return text, False


def _extract_pdf_sync(file_path: str) -> tuple[str, bool]:
    """Extract text from a PDF file with markdown structure preservation.

    Uses PyMuPDF dict mode to detect headings (by font size/bold) and
    format output with markdown headers. Falls back to OCR for scanned PDFs.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Tuple of (markdown-formatted text from all pages, whether OCR was applied).
    """
    import fitz

    doc = fitz.open(file_path)
    pages: list[str] = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_dict: dict[str, Any] = page.get_text("dict")  # pyright: ignore[reportUnknownMemberType, reportAssignmentType]
        blocks: list[dict[str, Any]] = page_dict["blocks"]
        page_lines: list[str] = []
        for block in blocks:
            if block["type"] != 0:  # skip non-text blocks
                continue
            for line in block["lines"]:
                spans: list[dict[str, Any]] = line["spans"]
                text = "".join(str(span["text"]) for span in spans)
                if not text.strip():
                    continue
                max_size: float = max(float(span["size"]) for span in spans)
                is_bold = any("bold" in str(span.get("font", "")).lower() for span in spans)
                if max_size >= 16 and is_bold:
                    page_lines.append(f"## {text.strip()}")
                elif max_size >= 14 and is_bold:
                    page_lines.append(f"### {text.strip()}")
                elif is_bold and len(text.strip()) < 100:
                    page_lines.append(f"**{text.strip()}**")
                else:
                    page_lines.append(text.strip())
        if page_lines:
            pages.append(f"# Page {page_num}\n\n" + "\n\n".join(page_lines))

    total_text = "\n\n".join(pages)

    # If sufficient text was extracted, return without OCR
    if len(total_text.strip()) >= 50:
        doc.close()
        return total_text, False

    # Scanned PDF detected — fall back to OCR
    page_count = len(doc)
    logger.info(
        "knowledge.extraction.ocr_fallback",
        file_path=file_path,
        page_count=page_count,
        extracted_chars=len(total_text.strip()),
    )

    try:
        import pytesseract
        from PIL import Image

        ocr_pages: list[str] = []
        # Limit to first 50 pages to avoid memory issues
        max_ocr_pages = min(page_count, 50)
        for i in range(max_ocr_pages):
            page = doc[i]
            pix = page.get_pixmap(dpi=300)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            ocr_text = str(pytesseract.image_to_string(image, lang="lav+eng"))
            if ocr_text.strip():
                ocr_pages.append(ocr_text)

        doc.close()
        result = "\n\n".join(ocr_pages)
        logger.info(
            "knowledge.extraction.ocr_completed",
            char_count=len(result),
            pages_ocrd=max_ocr_pages,
        )
        return result, True

    except Exception as e:
        doc.close()
        logger.warning(
            "knowledge.extraction.ocr_failed",
            file_path=file_path,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        # Return whatever text we got (possibly empty)
        return total_text, False


def _extract_docx_sync(file_path: str) -> str:
    """Extract text from a Word document with markdown structure.

    Maps Word heading styles to markdown headers, list styles to bullets,
    and extracts tables as markdown tables.

    Args:
        file_path: Path to the .docx file.

    Returns:
        Markdown-formatted document text.
    """
    from docx import Document as DocxDocument

    doc = DocxDocument(file_path)
    lines: list[str] = []
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        style = para.style.name if para.style else ""
        if style.startswith("Heading 1"):
            lines.append(f"# {para.text}")
        elif style.startswith("Heading 2"):
            lines.append(f"## {para.text}")
        elif style.startswith("Heading 3"):
            lines.append(f"### {para.text}")
        elif style.startswith("Heading"):
            parts = style.split()
            level = min(int(parts[-1]) if parts[-1].isdigit() else 4, 6)
            lines.append(f"{'#' * level} {para.text}")
        elif style.startswith("List"):
            lines.append(f"- {para.text}")
        else:
            lines.append(para.text)
    # Extract tables as markdown
    for table in doc.tables:
        if not table.rows:
            continue
        headers = [cell.text.strip().replace("|", "\\|") for cell in table.rows[0].cells]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in table.rows[1:]:
            cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n\n".join(lines)


def _extract_email_sync(file_path: str) -> str:
    """Extract text from an email file (.eml) with markdown formatting.

    Headers are formatted as bold markdown, body text follows.

    Args:
        file_path: Path to the email file.

    Returns:
        Markdown-formatted email headers and body text.
    """
    with Path(file_path).open() as f:
        msg = email_lib.message_from_file(f)

    parts: list[str] = []

    # Extract headers as bold markdown
    for header in ("From", "To", "Date", "Subject"):
        value = msg.get(header)
        if value:
            parts.append(f"**{header}:** {value}")

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
    """Extract text from an image via OCR, wrapped in markdown blockquote.

    Uses Latvian + English language packs for multilingual support.

    Args:
        file_path: Path to the image file.

    Returns:
        OCR-extracted text with markdown blockquote context.
    """
    import pytesseract
    from PIL import Image

    image = Image.open(file_path)
    raw = str(pytesseract.image_to_string(image, lang="lav+eng"))
    filename = Path(file_path).name
    return f"> OCR extracted from: {filename}\n\n{raw}"


def _extract_text_sync(file_path: str) -> str:
    """Read a plain text file.

    Args:
        file_path: Path to the text file.

    Returns:
        File content as string.
    """
    return Path(file_path).read_text(encoding="utf-8")


def _extract_excel_sync(file_path: str) -> str:
    """Extract Excel data as markdown tables.

    Each sheet becomes a section with a heading and a markdown table.

    Args:
        file_path: Path to the .xlsx file.

    Returns:
        Markdown-formatted tables from all sheets.
    """
    import openpyxl

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    sheets: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        all_rows = list(ws.iter_rows())
        if not all_rows:
            continue
        headers = [
            str(c.value).replace("|", "\\|") if c.value is not None else "" for c in all_rows[0]
        ]
        section_lines: list[str] = [f"## {sheet_name}", ""]
        section_lines.append("| " + " | ".join(headers) + " |")
        section_lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in all_rows[1:]:
            cells = [str(c.value).replace("|", "\\|") if c.value is not None else "" for c in row]
            section_lines.append("| " + " | ".join(cells) + " |")
        sheets.append("\n".join(section_lines))
    wb.close()
    return "\n\n".join(sheets)


def _extract_csv_sync(file_path: str) -> str:
    """Extract CSV data as a markdown table.

    First row is treated as headers. Pipe characters in cells are escaped.

    Args:
        file_path: Path to the CSV file.

    Returns:
        Markdown-formatted table.
    """
    import csv

    try:
        with Path(file_path).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            all_rows = list(reader)
            if not all_rows:
                return ""
            headers = [c.replace("|", "\\|") for c in all_rows[0]]
            lines: list[str] = []
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in all_rows[1:]:
                cells = [c.replace("|", "\\|") for c in row]
                lines.append("| " + " | ".join(cells) + " |")
            return "\n".join(lines)
    except csv.Error:
        logger.warning("knowledge.extraction.csv_fallback", file_path=file_path)
        return Path(file_path).read_text(encoding="utf-8")
