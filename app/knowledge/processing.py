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
        "pptx": _extract_pptx_sync,
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
    """Extract text from a PDF with table and multi-column layout preservation.

    Uses pdfplumber for primary extraction:
    - Tables are detected via ``page.find_tables()`` and emitted as markdown
      tables so the downstream semantic chunker classifies them correctly.
    - Prose is extracted via ``page.crop().extract_text()`` on regions between
      tables, which handles multi-column layouts better than raw block order.
    - Tables and prose are interleaved by y-coordinate to preserve document
      reading order.

    Falls back to tesseract OCR (lav+eng) via PyMuPDF rasterization when
    pdfplumber extracts less than 50 characters (scanned PDF detection).

    Args:
        file_path: Path to the PDF file.

    Returns:
        Tuple of (markdown-formatted text from all pages, whether OCR was applied).
    """
    import pdfplumber

    pages: list[str] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                content = _extract_pdf_page_content(page)
                if content.strip():
                    pages.append(f"# Page {page_num}\n\n{content}")
    except Exception as e:
        logger.warning(
            "knowledge.extraction.pdfplumber_failed",
            file_path=file_path,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

    total_text = "\n\n".join(pages)

    # If sufficient text was extracted, return without OCR
    if len(total_text.strip()) >= 50:
        return total_text, False

    # Scanned PDF detected — fall back to OCR via PyMuPDF rasterization
    import fitz

    doc = fitz.open(file_path)
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


def _extract_pdf_page_content(page: Any) -> str:  # noqa: ANN401 — pdfplumber lacks py.typed
    """Extract a pdfplumber page's content as markdown.

    Detects tables, extracts them as markdown, and extracts prose from
    the vertical gaps between (and around) tables in top-to-bottom order.

    Args:
        page: A pdfplumber ``Page`` object.

    Returns:
        Markdown-formatted page content with tables interleaved between prose.
    """
    parts: list[str] = []

    try:
        tables = list(page.find_tables())
    except Exception:
        tables = []

    tables_sorted = sorted(tables, key=lambda t: float(t.bbox[1]))

    page_width = float(page.width)
    page_height = float(page.height)
    prev_bottom = 0.0

    for table in tables_sorted:
        t_top = float(table.bbox[1])
        t_bottom = float(table.bbox[3])

        # Extract prose above this table (between the previous table and this one)
        if t_top > prev_bottom + 1:
            region_top = max(0.0, prev_bottom)
            region_bottom = min(page_height, t_top)
            prose = _safe_extract_text(page, 0.0, region_top, page_width, region_bottom)
            if prose:
                parts.append(prose)

        # Extract the table as markdown
        try:
            rows = table.extract()
        except Exception:
            rows = []
        md = _pdf_table_to_markdown(rows)
        if md:
            parts.append(md)

        prev_bottom = max(prev_bottom, t_bottom)

    # Extract prose after the last table (or full page if no tables were found)
    if prev_bottom < page_height - 1:
        prose = _safe_extract_text(page, 0.0, prev_bottom, page_width, page_height)
        if prose:
            parts.append(prose)

    return "\n\n".join(parts)


def _safe_extract_text(
    page: Any,  # noqa: ANN401 — pdfplumber lacks py.typed
    x0: float,
    top: float,
    x1: float,
    bottom: float,
) -> str:
    """Crop a pdfplumber page to a bbox and extract text, empty on any error."""
    try:
        crop = page.crop((x0, top, x1, bottom))
        text = crop.extract_text() or ""
        return str(text).strip()
    except Exception:
        return ""


def _pdf_table_to_markdown(rows: list[list[str | None]]) -> str:
    """Convert a pdfplumber table (rows of cells) to a markdown table.

    The first row is treated as the header. ``None`` cells become empty
    strings, pipe characters are escaped, and embedded newlines are replaced
    with spaces to keep the markdown on clean lines. Rows shorter or longer
    than the header are padded or truncated to match.

    Args:
        rows: Table rows as returned by ``pdfplumber.Table.extract()``.

    Returns:
        Markdown table string, or empty string if ``rows`` is empty.
    """
    if not rows:
        return ""

    header = [_clean_pdf_cell(c) for c in rows[0]]
    if not header:
        return ""

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        cells = [_clean_pdf_cell(c) for c in row]
        if len(cells) < len(header):
            cells = cells + [""] * (len(header) - len(cells))
        elif len(cells) > len(header):
            cells = cells[: len(header)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _clean_pdf_cell(cell: str | None) -> str:
    """Clean a PDF table cell for inclusion in a markdown table."""
    if cell is None:
        return ""
    return str(cell).strip().replace("|", "\\|").replace("\n", " ")


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


def _extract_pptx_sync(file_path: str) -> str:
    """Extract text from a PowerPoint deck as markdown.

    Emits one ``# Slide N: {title}`` heading per slide so the semantic chunker
    treats each slide as a section boundary. Body text becomes paragraphs,
    multi-paragraph shapes render as bulleted lists, tables become markdown
    pipe tables, and speaker notes are appended as ``**Notes:** {text}``.

    Args:
        file_path: Path to the .pptx file.

    Returns:
        Markdown-formatted deck text preserving slide order.
    """
    from pptx import Presentation

    pres = Presentation(file_path)
    parts: list[str] = []

    for idx, slide in enumerate(pres.slides, start=1):
        title_text = _pptx_slide_title(slide)
        heading = f"# Slide {idx}: {title_text}" if title_text else f"# Slide {idx}"
        parts.append(heading)

        body_blocks = _pptx_collect_shape_text(slide.shapes, skip_title=True)
        parts.extend(body_blocks)

        notes = _pptx_extract_notes(slide)
        if notes:
            parts.append(f"**Notes:** {notes}")

    return "\n\n".join(parts)


def _pptx_slide_title(slide: Any) -> str:  # noqa: ANN401 — python-pptx lacks py.typed
    """Return the slide title text, or empty string if none."""
    shapes = getattr(slide, "shapes", None)
    title_shape = getattr(shapes, "title", None) if shapes is not None else None
    text = getattr(title_shape, "text", "") if title_shape is not None else ""
    return str(text).strip()


def _pptx_collect_shape_text(
    shapes: Any,  # noqa: ANN401 — python-pptx lacks py.typed
    skip_title: bool,
) -> list[str]:
    """Recursively flatten shapes (including grouped shapes) into markdown blocks."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    blocks: list[str] = []
    for shape in shapes:
        shape_type = getattr(shape, "shape_type", None)
        if shape_type == MSO_SHAPE_TYPE.GROUP:
            blocks.extend(_pptx_collect_shape_text(shape.shapes, skip_title=False))
            continue

        if getattr(shape, "has_table", False):
            blocks.append(_pptx_table_to_markdown(shape.table))
            continue

        if not getattr(shape, "has_text_frame", False):
            continue

        is_title = (
            getattr(shape, "is_placeholder", False)
            and getattr(getattr(shape, "placeholder_format", None), "idx", None) == 0
        )
        if skip_title and is_title:
            continue

        paragraphs = [p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip()]
        if not paragraphs:
            continue
        if len(paragraphs) > 1:
            blocks.append("\n".join(f"- {line}" for line in paragraphs))
        else:
            blocks.append(paragraphs[0])

    return blocks


def _pptx_table_to_markdown(table: Any) -> str:  # noqa: ANN401 — python-pptx lacks py.typed
    """Render a python-pptx table as a GitHub markdown pipe table."""
    rows = list(table.rows)
    if not rows:
        return ""

    def cell_text(cell: Any) -> str:  # noqa: ANN401 — python-pptx lacks py.typed
        raw = str(getattr(cell, "text", "")).strip()
        return raw.replace("|", "\\|").replace("\n", " ")

    header = [cell_text(c) for c in rows[0].cells]
    if not header:
        return ""

    body = [[cell_text(c) for c in row.cells] for row in rows[1:]]

    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _pptx_extract_notes(slide: Any) -> str:  # noqa: ANN401 — python-pptx lacks py.typed
    """Extract speaker notes as plain text, or empty string."""
    if not getattr(slide, "has_notes_slide", False):
        return ""
    notes_slide = slide.notes_slide
    tf = getattr(notes_slide, "notes_text_frame", None)
    text = getattr(tf, "text", "") if tf is not None else ""
    return str(text).strip()


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
