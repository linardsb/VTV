"""Shared test factories and helpers for transit tests."""

from __future__ import annotations

import io
import zipfile


def make_eticket_line(
    *,
    record_id: str = "REC001",
    depot: str = "Riga-1",
    transport_type: str = "bus",
    vehicle_number: str = "4521",
    route_name: str = "Route 22",
    route_code: str = "22",
    direction: str = "A",
    validation_id: str = "VAL001",
    validated_at: str = "2026-01-15 08:30:00",
) -> str:
    """Build a single semicolon-delimited e-ticket TXT line."""
    return ";".join(
        [
            record_id,
            depot,
            transport_type,
            vehicle_number,
            route_name,
            route_code,
            direction,
            validation_id,
            validated_at,
        ]
    )


def make_eticket_txt(lines: list[str], *, encoding: str = "latin-1") -> bytes:
    """Build in-memory TXT content with header."""
    header = (
        "record_id;depot;transport_type;vehicle_number;"
        "route_name;route_code;direction;validation_id;validated_at"
    )
    content = "\n".join([header, *lines])
    return content.encode(encoding)


def make_eticket_zip(txt_files: dict[str, bytes]) -> bytes:
    """Build in-memory ZIP archive with named TXT files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in txt_files.items():
            zf.writestr(name, data)
    return buf.getvalue()
