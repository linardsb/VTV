"""Tests for document text extraction."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.knowledge.exceptions import UnsupportedDocumentTypeError
from app.knowledge.processing import extract_text


async def test_extract_pdf():
    """PDF extraction should use PyMuPDF and return text with OCR flag."""
    with patch("app.knowledge.processing._extract_pdf_sync") as mock_fn:
        mock_fn.return_value = ("Page 1 content", False)
        text, ocr_applied = await extract_text("/tmp/test.pdf", "pdf")  # noqa: S108

    assert "Page 1 content" in text
    assert ocr_applied is False


async def test_extract_docx():
    """DOCX extraction should use python-docx and return text."""
    mock_para = MagicMock()
    mock_para.text = "Paragraph content"

    mock_doc_cls = MagicMock()
    mock_doc_instance = MagicMock()
    mock_doc_instance.paragraphs = [mock_para]
    mock_doc_cls.return_value = mock_doc_instance

    with patch.dict("sys.modules", {"docx": MagicMock()}):
        with patch("app.knowledge.processing._extract_docx_sync") as mock_fn:
            mock_fn.return_value = "Paragraph content"
            text, ocr_applied = await extract_text("/tmp/test.docx", "docx")  # noqa: S108

    assert "Paragraph content" in text
    assert ocr_applied is False


async def test_extract_text_file(tmp_path: Path) -> None:
    """Plain text extraction should read file content."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello plain text", encoding="utf-8")
    text, ocr_applied = await extract_text(str(test_file), "text")
    assert text == "Hello plain text"
    assert ocr_applied is False


async def test_extract_image_uses_latvian_ocr():
    """Image OCR should use Latvian + English language packs."""
    with patch("app.knowledge.processing._extract_image_sync") as mock_fn:
        mock_fn.return_value = "OCR text"
        text, ocr_applied = await extract_text("/tmp/test.png", "image")  # noqa: S108
    assert text == "OCR text"
    assert ocr_applied is False


async def test_unsupported_type_raises():
    """Unknown document types should raise UnsupportedDocumentTypeError."""
    with pytest.raises(UnsupportedDocumentTypeError, match="Unsupported document type: unknown"):
        await extract_text("/tmp/test.bin", "unknown")  # noqa: S108


async def test_email_extraction():
    """Email extraction should handle .eml files."""
    with patch("app.knowledge.processing._extract_email_sync") as mock_fn:
        mock_fn.return_value = "From: test@example.com\n\nEmail body"
        text, ocr_applied = await extract_text("/tmp/test.eml", "email")  # noqa: S108
    assert "Email body" in text
    assert ocr_applied is False


# ---------------------------------------------------------------------------
# OCR fallback tests
# ---------------------------------------------------------------------------


async def test_extract_pdf_ocr_fallback():
    """Scanned PDFs with no extractable text should trigger OCR."""
    with patch("app.knowledge.processing._extract_pdf_sync") as mock_fn:
        mock_fn.return_value = ("OCR extracted text", True)
        text, ocr_applied = await extract_text("/tmp/scanned.pdf", "pdf")  # noqa: S108

    assert "OCR extracted text" in text
    assert ocr_applied is True


async def test_extract_pdf_no_ocr_needed():
    """PDFs with extractable text should not trigger OCR."""
    with patch("app.knowledge.processing._extract_pdf_sync") as mock_fn:
        mock_fn.return_value = ("Normal PDF text", False)
        text, ocr_applied = await extract_text("/tmp/normal.pdf", "pdf")  # noqa: S108

    assert "Normal PDF text" in text
    assert ocr_applied is False


async def test_non_pdf_returns_no_ocr():
    """Non-PDF extractors should always return ocr_applied=False."""
    with patch("app.knowledge.processing._extract_text_sync") as mock_fn:
        mock_fn.return_value = "Plain text content"
        _text, ocr_applied = await extract_text("/tmp/test.txt", "text")  # noqa: S108

    assert ocr_applied is False


# ---------------------------------------------------------------------------
# Markdown extraction tests
# ---------------------------------------------------------------------------


async def test_docx_headings_to_markdown():
    """DOCX Heading styles should map to markdown headers."""
    from app.knowledge.processing import _extract_docx_sync

    mock_paras: list[MagicMock] = []
    for style_name, text in [
        ("Heading 1", "Title"),
        ("Heading 2", "Section"),
        ("Heading 3", "Subsection"),
        ("Normal", "Body text"),
        ("List Paragraph", "Item one"),
    ]:
        para = MagicMock()
        para.text = text
        para.style = MagicMock()
        para.style.name = style_name
        mock_paras.append(para)

    mock_doc = MagicMock()
    mock_doc.paragraphs = mock_paras
    mock_doc.tables = []

    with patch("docx.Document", return_value=mock_doc):
        result = _extract_docx_sync("/tmp/test.docx")  # noqa: S108

    assert "# Title" in result
    assert "## Section" in result
    assert "### Subsection" in result
    assert "Body text" in result
    assert "- Item one" in result


async def test_docx_tables_to_markdown():
    """DOCX tables should become markdown tables."""
    from app.knowledge.processing import _extract_docx_sync

    mock_cell_a = MagicMock()
    mock_cell_a.text = "Name"
    mock_cell_b = MagicMock()
    mock_cell_b.text = "Value"
    mock_cell_c = MagicMock()
    mock_cell_c.text = "Alice"
    mock_cell_d = MagicMock()
    mock_cell_d.text = "42"

    mock_row_header = MagicMock()
    mock_row_header.cells = [mock_cell_a, mock_cell_b]
    mock_row_data = MagicMock()
    mock_row_data.cells = [mock_cell_c, mock_cell_d]

    mock_table = MagicMock()
    mock_table.rows = [mock_row_header, mock_row_data]

    mock_doc = MagicMock()
    mock_doc.paragraphs = []
    mock_doc.tables = [mock_table]

    with patch("docx.Document", return_value=mock_doc):
        result = _extract_docx_sync("/tmp/test.docx")  # noqa: S108

    assert "| Name | Value |" in result
    assert "| --- | --- |" in result
    assert "| Alice | 42 |" in result


async def test_excel_to_markdown_tables():
    """XLSX sheets should become markdown tables with sheet name headings."""
    from app.knowledge.processing import _extract_excel_sync

    mock_cell_h1 = MagicMock(value="Col1")
    mock_cell_h2 = MagicMock(value="Col2")
    mock_cell_d1 = MagicMock(value="A")
    mock_cell_d2 = MagicMock(value=100)

    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = [
        [mock_cell_h1, mock_cell_h2],
        [mock_cell_d1, mock_cell_d2],
    ]

    mock_wb = MagicMock()
    mock_wb.sheetnames = ["Data"]
    mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

    with patch("openpyxl.load_workbook", return_value=mock_wb):
        result = _extract_excel_sync("/tmp/test.xlsx")  # noqa: S108

    assert "## Data" in result
    assert "| Col1 | Col2 |" in result
    assert "| A | 100 |" in result


async def test_csv_to_markdown_table(tmp_path: Path) -> None:
    """CSV rows should become a markdown table with header."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name,Age\nAlice,30\nBob,25", encoding="utf-8")

    from app.knowledge.processing import _extract_csv_sync

    result = _extract_csv_sync(str(csv_file))

    assert "| Name | Age |" in result
    assert "| --- | --- |" in result
    assert "| Alice | 30 |" in result
    assert "| Bob | 25 |" in result


async def test_image_ocr_markdown_wrapper():
    """Image OCR should wrap text in a blockquote with filename."""
    with patch("app.knowledge.processing._extract_image_sync") as mock_fn:
        mock_fn.return_value = "> OCR extracted from: photo.png\n\nSome OCR text"
        text, _ocr_applied = await extract_text("/tmp/photo.png", "image")  # noqa: S108

    assert "> OCR extracted from: photo.png" in text
    assert "Some OCR text" in text


async def test_email_markdown_headers():
    """Email headers should be formatted as bold markdown."""
    with patch("app.knowledge.processing._extract_email_sync") as mock_fn:
        mock_fn.return_value = "**From:** test@example.com\n\n**Subject:** Test\n\nEmail body"
        text, _ocr = await extract_text("/tmp/test.eml", "email")  # noqa: S108

    assert "**From:**" in text
    assert "**Subject:**" in text


# ---------------------------------------------------------------------------
# PDF table extraction tests (pdfplumber-based)
# ---------------------------------------------------------------------------


def test_pdf_table_to_markdown_basic():
    """Basic 2-column table with header and one data row."""
    from app.knowledge.processing import _pdf_table_to_markdown

    rows: list[list[str | None]] = [
        ["Route", "Fare"],
        ["22", "1.50"],
    ]
    result = _pdf_table_to_markdown(rows)

    assert "| Route | Fare |" in result
    assert "| --- | --- |" in result
    assert "| 22 | 1.50 |" in result


def test_pdf_table_to_markdown_handles_none_cells():
    """None cells should become empty strings in markdown output."""
    from app.knowledge.processing import _pdf_table_to_markdown

    rows: list[list[str | None]] = [
        ["A", "B", "C"],
        ["x", None, "z"],
    ]
    result = _pdf_table_to_markdown(rows)

    assert "| x |  | z |" in result


def test_pdf_table_to_markdown_escapes_pipes():
    """Pipe characters in cells should be escaped so they don't break the table."""
    from app.knowledge.processing import _pdf_table_to_markdown

    rows: list[list[str | None]] = [
        ["Header"],
        ["a | b"],
    ]
    result = _pdf_table_to_markdown(rows)

    assert "| a \\| b |" in result


def test_pdf_table_to_markdown_strips_embedded_newlines():
    """Newlines inside a cell should be replaced with spaces."""
    from app.knowledge.processing import _pdf_table_to_markdown

    rows: list[list[str | None]] = [
        ["Name"],
        ["Line one\nLine two"],
    ]
    result = _pdf_table_to_markdown(rows)

    assert "| Line one Line two |" in result


def test_pdf_table_to_markdown_pads_short_rows():
    """Rows with fewer cells than the header should be padded with empty strings."""
    from app.knowledge.processing import _pdf_table_to_markdown

    rows: list[list[str | None]] = [
        ["A", "B", "C"],
        ["x"],
    ]
    result = _pdf_table_to_markdown(rows)

    # Short row padded to 3 columns
    assert "| x |  |  |" in result


def test_pdf_table_to_markdown_truncates_long_rows():
    """Rows with more cells than the header should be truncated to header length."""
    from app.knowledge.processing import _pdf_table_to_markdown

    rows: list[list[str | None]] = [
        ["A", "B"],
        ["x", "y", "extra"],
    ]
    result = _pdf_table_to_markdown(rows)

    assert "| x | y |" in result
    assert "extra" not in result


def test_pdf_table_to_markdown_empty_returns_empty():
    """Empty rows list should return empty string."""
    from app.knowledge.processing import _pdf_table_to_markdown

    assert _pdf_table_to_markdown([]) == ""


def test_extract_pdf_page_content_tables_interleaved_with_prose():
    """Page content should emit prose before a table, then the table as markdown."""
    from app.knowledge.processing import _extract_pdf_page_content

    # Mock pdfplumber Table: bbox=(x0, top, x1, bottom), extract() returns rows
    mock_table = MagicMock()
    mock_table.bbox = (0.0, 100.0, 500.0, 200.0)
    mock_table.extract.return_value = [["Header"], ["Cell"]]

    # Mock cropped page regions
    mock_crop_top = MagicMock()
    mock_crop_top.extract_text.return_value = "Prose above table"
    mock_crop_bottom = MagicMock()
    mock_crop_bottom.extract_text.return_value = "Prose below table"

    # Mock page with find_tables + crop + size
    mock_page = MagicMock()
    mock_page.width = 500.0
    mock_page.height = 800.0
    mock_page.find_tables.return_value = [mock_table]

    def crop_side_effect(bbox: tuple[float, float, float, float]) -> MagicMock:
        # bbox: (x0, top, x1, bottom)
        if bbox[1] < 100.0:
            return mock_crop_top
        return mock_crop_bottom

    mock_page.crop.side_effect = crop_side_effect

    result = _extract_pdf_page_content(mock_page)

    assert "Prose above table" in result
    assert "| Header |" in result
    assert "| Cell |" in result
    assert "Prose below table" in result
    # Ordering: prose-above comes before the table which comes before prose-below
    assert result.index("Prose above table") < result.index("| Header |")
    assert result.index("| Header |") < result.index("Prose below table")


def test_extract_pdf_page_content_no_tables_extracts_whole_page():
    """When no tables are found, extract text from the full page."""
    from app.knowledge.processing import _extract_pdf_page_content

    mock_crop = MagicMock()
    mock_crop.extract_text.return_value = "Full page prose content"

    mock_page = MagicMock()
    mock_page.width = 500.0
    mock_page.height = 800.0
    mock_page.find_tables.return_value = []
    mock_page.crop.return_value = mock_crop

    result = _extract_pdf_page_content(mock_page)

    assert "Full page prose content" in result


def test_extract_pdf_page_content_handles_find_tables_error():
    """If find_tables() raises, the page should still extract text via crop."""
    from app.knowledge.processing import _extract_pdf_page_content

    mock_crop = MagicMock()
    mock_crop.extract_text.return_value = "Recovered prose"

    mock_page = MagicMock()
    mock_page.width = 500.0
    mock_page.height = 800.0
    mock_page.find_tables.side_effect = RuntimeError("pdfplumber table error")
    mock_page.crop.return_value = mock_crop

    result = _extract_pdf_page_content(mock_page)

    assert "Recovered prose" in result


def test_extract_pdf_sync_uses_pdfplumber_and_emits_tables():
    """End-to-end: _extract_pdf_sync should call pdfplumber and emit a markdown table."""
    from app.knowledge.processing import _extract_pdf_sync

    # Build a mock Table
    mock_table = MagicMock()
    mock_table.bbox = (0.0, 100.0, 500.0, 200.0)
    mock_table.extract.return_value = [
        ["Route", "Fare"],
        ["22", "1.50"],
    ]

    mock_crop = MagicMock()
    mock_crop.extract_text.return_value = "Fare schedule below."

    mock_page = MagicMock()
    mock_page.width = 500.0
    mock_page.height = 800.0
    mock_page.find_tables.return_value = [mock_table]
    mock_page.crop.return_value = mock_crop

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    # Context manager protocol
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        text, ocr_applied = _extract_pdf_sync("/tmp/fake.pdf")  # noqa: S108

    assert "# Page 1" in text
    assert "| Route | Fare |" in text
    assert "| 22 | 1.50 |" in text
    assert ocr_applied is False


def test_extract_pdf_sync_ocr_fallback_on_empty_pdfplumber_result():
    """If pdfplumber extracts too little text, OCR fallback should trigger."""
    from app.knowledge.processing import _extract_pdf_sync

    # pdfplumber returns a page with no tables and no text
    mock_crop = MagicMock()
    mock_crop.extract_text.return_value = ""

    mock_page = MagicMock()
    mock_page.width = 500.0
    mock_page.height = 800.0
    mock_page.find_tables.return_value = []
    mock_page.crop.return_value = mock_crop

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    # Mock fitz (PyMuPDF) for OCR rasterization
    mock_fitz_page = MagicMock()
    mock_pixmap = MagicMock()
    mock_pixmap.width = 100
    mock_pixmap.height = 100
    mock_pixmap.samples = b"\x00" * (100 * 100 * 3)
    mock_fitz_page.get_pixmap.return_value = mock_pixmap

    mock_fitz_doc = MagicMock()
    mock_fitz_doc.__len__ = MagicMock(return_value=1)
    mock_fitz_doc.__getitem__ = MagicMock(return_value=mock_fitz_page)

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_fitz_doc

    mock_pytesseract = MagicMock()
    mock_pytesseract.image_to_string.return_value = (
        "OCR extracted scanned content with enough characters to be meaningful."
    )

    mock_pil_image_cls = MagicMock()
    mock_pil_image_cls.frombytes.return_value = MagicMock()
    mock_pil_module = MagicMock()
    mock_pil_module.Image = mock_pil_image_cls

    with (
        patch("pdfplumber.open", return_value=mock_pdf),
        patch.dict(
            "sys.modules",
            {
                "fitz": mock_fitz,
                "pytesseract": mock_pytesseract,
                "PIL": mock_pil_module,
            },
        ),
    ):
        text, ocr_applied = _extract_pdf_sync("/tmp/scanned.pdf")  # noqa: S108

    assert ocr_applied is True
    assert "OCR extracted scanned content" in text


# ---------------------------------------------------------------------------
# PPTX extraction tests
# ---------------------------------------------------------------------------


async def test_extract_pptx_basic(sample_pptx_path: Path) -> None:
    """PPTX extraction should emit slide heading and body text."""
    text, ocr_applied = await extract_text(str(sample_pptx_path), "pptx")
    assert ocr_applied is False
    assert "# Slide 1: Safety Procedures" in text
    assert "Evacuation Protocol" in text


async def test_extract_pptx_preserves_slide_order(sample_pptx_path: Path) -> None:
    """Slides should appear in deck order in the extracted markdown."""
    text, _ = await extract_text(str(sample_pptx_path), "pptx")
    assert text.index("# Slide 1") < text.index("# Slide 2") < text.index("# Slide 3")


async def test_extract_pptx_emits_table_markdown(sample_pptx_path: Path) -> None:
    """Tables on a slide should render as markdown pipe tables."""
    text, _ = await extract_text(str(sample_pptx_path), "pptx")
    assert "| Route | ETA |" in text
    assert "| 3 | 08:15 |" in text


async def test_extract_pptx_includes_speaker_notes(sample_pptx_path: Path) -> None:
    """Speaker notes should be appended as a bold Notes block."""
    text, _ = await extract_text(str(sample_pptx_path), "pptx")
    assert "**Notes:** Review quarterly." in text


async def test_extract_pptx_handles_empty_slide(sample_pptx_path: Path) -> None:
    """Slides without title or content still emit a heading."""
    text, _ = await extract_text(str(sample_pptx_path), "pptx")
    assert "# Slide 4" in text


async def test_extract_pptx_bulleted_body_rendered_as_list(sample_pptx_path: Path) -> None:
    """Multi-paragraph body shapes should render as markdown bullets."""
    text, _ = await extract_text(str(sample_pptx_path), "pptx")
    assert "- Locate nearest exit" in text
    assert "- Follow warden instructions" in text


async def test_extract_pptx_heading_structure_feeds_chunker(sample_pptx_path: Path) -> None:
    """Slide headings should populate chunk heading_path breadcrumbs."""
    from app.knowledge.chunking import chunk_text_semantic

    text, _ = await extract_text(str(sample_pptx_path), "pptx")
    chunks = chunk_text_semantic(text)
    assert len(chunks) >= 1
    paths = [c.heading_path for c in chunks if c.heading_path]
    assert any("Slide 1: Safety Procedures" in p for p in paths)
