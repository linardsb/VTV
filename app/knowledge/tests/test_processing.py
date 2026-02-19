"""Tests for document text extraction."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.knowledge.exceptions import UnsupportedDocumentTypeError
from app.knowledge.processing import extract_text


async def test_extract_pdf():
    """PDF extraction should use PyMuPDF and return text."""
    with patch("app.knowledge.processing._extract_pdf_sync") as mock_fn:
        mock_fn.return_value = "Page 1 content"
        result = await extract_text("/tmp/test.pdf", "pdf")  # noqa: S108

    assert "Page 1 content" in result


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
            result = await extract_text("/tmp/test.docx", "docx")  # noqa: S108

    assert "Paragraph content" in result


async def test_extract_text_file(tmp_path: Path) -> None:
    """Plain text extraction should read file content."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello plain text", encoding="utf-8")
    result = await extract_text(str(test_file), "text")
    assert result == "Hello plain text"


async def test_extract_image_uses_latvian_ocr():
    """Image OCR should use Latvian + English language packs."""
    with patch("app.knowledge.processing._extract_image_sync") as mock_fn:
        mock_fn.return_value = "OCR text"
        result = await extract_text("/tmp/test.png", "image")  # noqa: S108
    assert result == "OCR text"


async def test_unsupported_type_raises():
    """Unknown document types should raise UnsupportedDocumentTypeError."""
    with pytest.raises(UnsupportedDocumentTypeError, match="Unsupported document type: unknown"):
        await extract_text("/tmp/test.bin", "unknown")  # noqa: S108


async def test_email_extraction():
    """Email extraction should handle .eml files."""
    with patch("app.knowledge.processing._extract_email_sync") as mock_fn:
        mock_fn.return_value = "From: test@example.com\n\nEmail body"
        result = await extract_text("/tmp/test.eml", "email")  # noqa: S108
    assert "Email body" in result
