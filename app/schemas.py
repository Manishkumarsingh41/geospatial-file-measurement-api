"""Pydantic response schemas for the Geospatial File Measurement API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FileSummary(BaseModel):
    """Returned after a successful upload."""

    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: str
    created_at: str | None = None


class FeatureResponse(BaseModel):
    """Detail about a single extracted feature."""

    feature_id: int
    geometry_type: str
    geometry: dict[str, Any] | None = None
    crs: str | None
    properties: dict[str, Any] = Field(default_factory=dict)


class MeasurementResponse(BaseModel):
    """Measurement result for a single feature."""

    feature_id: int
    geometry_type: str
    measurement_type: str | None = None
    value: float | None = None
    unit: str | None = None
    source_crs: str | None = None
    measurement_crs: str | None = None
    status: str
    reason: str | None = None


class FileDetailResponse(FileSummary):
    """Full file detail including extracted features."""

    features: list[FeatureResponse] = Field(default_factory=list)
