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
