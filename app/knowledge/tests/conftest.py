# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false
"""Test fixtures for knowledge base feature."""

from pathlib import Path

import pytest

from app.knowledge.schemas import DocumentUpload


@pytest.fixture
def sample_upload() -> DocumentUpload:
    """Provide a sample document upload schema."""
    return DocumentUpload(
        domain="transit", language="lv", metadata_json=None, title=None, description=None
    )


@pytest.fixture
def sample_latvian_text() -> str:
    """Provide multi-paragraph Latvian text with diacritics."""
    return (
        "Rigas Satiksme ir Latvijas galvaspilsetas sabiedriska transporta uznemums.\n\n"
        "Uznemums nodrosina autobusu, tramvaju un trolejbusu pakalpojumus visiem "
        "Rigas iedzivotajiem un viesiem.\n\n"
        "Marsrutu kartiba ir noteikta saskana ar pilsetas transporta planu. "
        "Katra marsruta grafiks tiek regulari atjaunots, lai nodrosinatu "
        "efektivu un ertu pakalpojumu."
    )


@pytest.fixture
def sample_english_text() -> str:
    """Provide multi-paragraph English text."""
    return (
        "Riga public transit operates bus, tram, and trolleybus services.\n\n"
        "The transit authority manages over 50 routes across the city. "
        "Each route has a designated schedule that is updated quarterly.\n\n"
        "Drivers must follow the prescribed route and maintain schedule adherence. "
        "Deviations must be reported to the dispatch center immediately."
    )


@pytest.fixture
def sample_pptx_path(tmp_path: Path) -> Path:
    """Build a 4-slide PPTX in-memory: title+bulleted body+notes, table, text box, empty."""
    from pptx import Presentation
    from pptx.util import Inches

    pres = Presentation()

    # Slide 1: title + bulleted body + speaker notes
    s1 = pres.slides.add_slide(pres.slide_layouts[1])
    s1.shapes.title.text = "Safety Procedures"
    tf = s1.placeholders[1].text_frame
    tf.text = "Evacuation Protocol"
    tf.add_paragraph().text = "Locate nearest exit"
    tf.add_paragraph().text = "Follow warden instructions"
    s1.notes_slide.notes_text_frame.text = "Review quarterly."

    # Slide 2: table
    s2 = pres.slides.add_slide(pres.slide_layouts[5])
    s2.shapes.title.text = "Schedule"
    rows, cols, left, top, width, height = 2, 2, Inches(1), Inches(1.5), Inches(6), Inches(2)
    table = s2.shapes.add_table(rows, cols, left, top, width, height).table
    table.cell(0, 0).text = "Route"
    table.cell(0, 1).text = "ETA"
    table.cell(1, 0).text = "3"
    table.cell(1, 1).text = "08:15"

    # Slide 3: extra text box
    s3 = pres.slides.add_slide(pres.slide_layouts[5])
    s3.shapes.title.text = "Nested Content"
    tb = s3.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1)).text_frame
    tb.text = "Extra note inside a text box"

    # Slide 4: empty layout
    pres.slides.add_slide(pres.slide_layouts[6])

    path = tmp_path / "sample.pptx"
    pres.save(str(path))
    return path
