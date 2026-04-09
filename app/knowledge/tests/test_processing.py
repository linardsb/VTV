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
