"""FastAPI application entry-point for the Geospatial File Measurement API."""

import logging

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="CRS-aware API for processing KML and zipped Shapefile data.",
)
app.include_router(router, prefix="/api")


@app.get("/health", tags=["system"], summary="Health check")
def health() -> dict[str, str]:
    """Return a simple liveness probe."""
    return {"status": "ok"}
