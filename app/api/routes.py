"""API routes for file upload, retrieval, and measurements."""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.repositories.file_repository import FileRepository
from app.schemas import FileDetailResponse, FileSummary, MeasurementResponse
from app.services.geospatial_service import GeoProcessingError, GeospatialService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])
repository = FileRepository(settings.upload_dir)
service = GeospatialService(repository)


@router.post(
    "/files/",
    response_model=FileSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a geospatial file",
    description="Upload a `.kml` or `.zip` (Shapefile) for processing.",
)
async def upload_file(file: UploadFile = File(...)) -> FileSummary:
    """Accept a KML or zipped Shapefile, extract features, and persist."""
    content = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB upload limit.",
        )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        record = service.process_upload(file.filename or "upload", content)
    except GeoProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return FileSummary(
        id=record.id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=record.status,
        created_at=record.created_at,
    )


@router.get(
    "/files/{file_id}/",
    response_model=FileDetailResponse,
    summary="Get file details",
    description="Retrieve metadata and extracted features for a processed file.",
)
def get_file(file_id: str) -> FileDetailResponse:
    """Return file metadata and feature-level detail."""
    record = repository.get(file_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found."
        )
    return FileDetailResponse(
        id=record.id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=record.status,
        created_at=record.created_at,
        features=service.get_features(record),
    )


@router.get(
    "/files/{file_id}/measurements/",
    response_model=list[MeasurementResponse],
    summary="Get measurements",
    description="Retrieve CRS-aware area/length measurements for all features.",
)
def get_measurements(file_id: str) -> list[MeasurementResponse]:
    """Return pre-computed measurements for every feature in the file."""
    record = repository.get(file_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found."
        )
    try:
        return service.get_measurements(record)
    except GeoProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
