"""Pydantic schemas for NeTEx/SIRI compliance export responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ExportFormat = Literal["NeTEx", "SIRI-VM", "SIRI-SM"]


class ExportMetadata(BaseModel):
    """Metadata returned by the compliance status endpoint.

    Attributes:
        format: Export format identifier.
        version: Standard version (e.g. "1.2" for NeTEx EPIP, "2.0" for SIRI).
        codespace: NeTEx codespace prefix for element IDs.
        generated_at: ISO 8601 timestamp of when metadata was generated.
        entity_counts: Count of entities available for export by type.
    """

    model_config = ConfigDict(strict=True)

    format: ExportFormat
    version: str
    codespace: str
    generated_at: str
    entity_counts: dict[str, int]
