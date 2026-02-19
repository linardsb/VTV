"""Test fixtures for knowledge base feature."""

import pytest

from app.knowledge.schemas import DocumentUpload


@pytest.fixture
def sample_upload() -> DocumentUpload:
    """Provide a sample document upload schema."""
    return DocumentUpload(domain="transit", language="lv", metadata_json=None)


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
