"""Pydantic schemas for NeTEx/SIRI compliance export responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ExportFormat = Literal["NeTEx", "SIRI-VM", "SIRI-SM"]

# OpenAPI response metadata for XML export endpoints.
# Used in route decorator `responses` params — NOT at runtime.
NETEX_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": "NeTEx EPIP v1.2 XML document",
        "content": {"application/xml": {"schema": {"type": "string"}}},
    },
}

SIRI_VM_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": "SIRI-VM 2.0 Vehicle Monitoring XML document",
        "content": {"application/xml": {"schema": {"type": "string"}}},
    },
}

SIRI_SM_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": "SIRI-SM 2.0 Stop Monitoring XML document",
        "content": {"application/xml": {"schema": {"type": "string"}}},
    },
}


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
