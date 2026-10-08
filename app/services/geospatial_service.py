"""Geospatial processing service.

Responsibilities:
  - Validate and read KML / zipped-Shapefile uploads.
  - Extract features with geometry, CRS, and properties.
  - Calculate area (Polygon/MultiPolygon) and length (LineString/MultiLineString)
    using a projected CRS so measurements are always in metres.

CRS Strategy
------------
The service **never** calculates area or length directly from geographic
(degree-based) coordinates such as EPSG:4326.

* If the source CRS is *projected* (``is_projected == True``), it is used
  directly — no transformation is needed.
* If the source CRS is *geographic*, the service estimates a local UTM zone
  via ``GeoDataFrame.estimate_utm_crs()`` and transforms the geometries into
  that UTM CRS before measuring.  UTM zones use metre-based coordinates and
  are accurate for regional datasets.

All area values are returned in **square metres (m²)** and all length values
in **metres (m)**.
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.repositories.file_repository import FileRecord, FileRepository

logger = logging.getLogger(__name__)


class GeoProcessingError(Exception):
    """Raised for any user-facing geospatial processing failure."""


class GeospatialService:
    """Orchestrates file validation, feature extraction, and measurements."""

    ALLOWED_EXTENSIONS: set[str] = {".kml", ".zip"}
    _REQUIRED_SHP_COMPANIONS: set[str] = {".shp", ".shx", ".dbf"}

    def __init__(self, repository: FileRepository) -> None:
        self.repository = repository

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_upload(self, filename: str, content: bytes) -> FileRecord:
        """Validate, parse, and persist an uploaded geospatial file.

        Returns the persisted ``FileRecord`` on success.
        Raises ``GeoProcessingError`` for any validation or parsing failure.
        """
        safe_name = self._sanitise_filename(filename)
        suffix = Path(safe_name).suffix.lower()

        if suffix not in self.ALLOWED_EXTENSIONS:
            raise GeoProcessingError(
                f"Unsupported file type '{suffix}'. Only .kml and .zip (Shapefile) are accepted."
            )

        if suffix == ".zip":
            self._validate_shapefile_archive(content)

        file_id = uuid.uuid4().hex
        work_dir = Path(tempfile.mkdtemp(prefix=f"geo_{file_id}_"))

        try:
            input_path = work_dir / safe_name
            input_path.write_bytes(content)

            gdf = self._read_geospatial_file(input_path, work_dir)
            if gdf.empty:
                raise GeoProcessingError("The uploaded file contains no features.")

            # Persist source file and serialised features.
            record_dir = Path(self.repository.root) / file_id
            record_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, record_dir / safe_name)

            record = FileRecord(
                id=file_id,
                filename=safe_name,
                stored_path=str(record_dir / safe_name),
                feature_count=len(gdf),
                crs=self._crs_label(gdf),
                status="COMPLETED",
                created_at=self.repository.now_iso(),
            )
            self.repository.add(record)

            features_json = json.dumps(
                self._serialise_features(gdf), ensure_ascii=False
            )
            (record_dir / "features.json").write_text(features_json, encoding="utf-8")

            # Pre-compute and cache measurements alongside features.
            measurements = self._compute_measurements(gdf)
            measurements_json = json.dumps(measurements, ensure_ascii=False)
            (record_dir / "measurements.json").write_text(
                measurements_json, encoding="utf-8"
            )

            logger.info(
                "Processed '%s' → %d features, CRS=%s",
                safe_name,
                len(gdf),
                record.crs,
            )
            return record

        except GeoProcessingError:
            raise
        except Exception as exc:
            logger.exception("Failed to process '%s'", safe_name)
            raise GeoProcessingError(
                f"Unable to process geospatial file: {exc}"
            ) from exc
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def get_features(self, record: FileRecord) -> list[dict[str, Any]]:
        """Return the cached feature list for a processed file."""
        path = Path(record.stored_path).parent / "features.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def get_measurements(self, record: FileRecord) -> list[dict[str, Any]]:
        """Return the cached measurements for a processed file."""
        path = Path(record.stored_path).parent / "measurements.json"
        return json.loads(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read_geospatial_file(
        self, path: Path, work_dir: Path
    ) -> gpd.GeoDataFrame:
        """Dispatch to the correct reader based on file extension."""
        ext = path.suffix.lower()
        if ext == ".kml":
            return self._read_kml(path)
        if ext == ".zip":
            return self._read_shapefile_zip(path, work_dir)
        raise GeoProcessingError(f"Unsupported file format: {ext}")

    @staticmethod
    def _read_kml(path: Path) -> gpd.GeoDataFrame:
        """Read a KML file via Fiona's KML driver.

        Handles the edge case where Fiona/GDAL raises an ``IndexError``
        for KML files that contain no Placemarks.
        """
        try:
            import fiona

            fiona.drvsupport.supported_drivers["KML"] = "r"
            gdf = gpd.read_file(path, driver="KML")
            return gdf
        except (IndexError, StopIteration):
            # Fiona raises IndexError for KML files with zero features.
            return gpd.GeoDataFrame()
        except Exception as exc:
            raise GeoProcessingError(
                f"Failed to read KML file: {exc}"
            ) from exc

    def _read_shapefile_zip(
        self, path: Path, work_dir: Path
    ) -> gpd.GeoDataFrame:
        """Extract and read a zipped Shapefile."""
        extract_root = (work_dir / "shapefile").resolve()
        extract_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(path) as archive:
            # Guard against zip-slip.
            for member in archive.infolist():
                target = (extract_root / member.filename).resolve()
                if not str(target).startswith(str(extract_root)):
                    raise GeoProcessingError(
                        "ZIP archive contains an unsafe path (path traversal detected)."
                    )
            archive.extractall(extract_root)

        shp = next(extract_root.rglob("*.shp"), None)
        if shp is None:
            raise GeoProcessingError("No .shp file found inside the ZIP archive.")

        try:
            return gpd.read_file(shp)
        except Exception as exc:
            raise GeoProcessingError(
                f"Failed to read Shapefile from ZIP: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitise_filename(filename: str) -> str:
        """Strip directory components and replace dangerous characters."""
        name = Path(filename).name  # drop any directory prefix
        # Replace anything that isn't alphanumeric, dot, hyphen, or underscore.
        safe = "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
        return safe or "upload"

    def _validate_shapefile_archive(self, content: bytes) -> None:
        """Ensure the ZIP is valid and contains at least .shp, .shx, .dbf."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                extensions = {Path(n).suffix.lower() for n in archive.namelist()}
                if not self._REQUIRED_SHP_COMPANIONS.issubset(extensions):
                    raise GeoProcessingError(
                        "ZIP must contain a valid Shapefile set (.shp, .shx, .dbf)."
                    )
        except zipfile.BadZipFile as exc:
            raise GeoProcessingError(
                "The uploaded file is not a valid ZIP archive."
            ) from exc

    # ------------------------------------------------------------------
    # CRS helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _measurement_crs(gdf: gpd.GeoDataFrame):
        """Determine the CRS to use for area/length calculations.

        * Projected CRS → used as-is.
        * Geographic CRS → estimate a local UTM zone.
        * No CRS → raise.
        """
        if gdf.crs is None:
            raise GeoProcessingError(
                "Input file has no CRS; measurements cannot be calculated safely."
            )
        if gdf.crs.is_projected:
            return gdf.crs
        try:
            estimated = gdf.estimate_utm_crs()
        except Exception as exc:
            raise GeoProcessingError(
                f"Unable to determine a suitable projected CRS: {exc}"
            ) from exc
        if estimated is None:
            raise GeoProcessingError(
                "Unable to determine a suitable projected CRS for measurement."
            )
        return estimated

    @staticmethod
    def _crs_label(gdf: gpd.GeoDataFrame) -> str | None:
        """Return a human-readable CRS identifier."""
        if gdf.crs is None:
            return None
        try:
            epsg = gdf.crs.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
        except Exception:
            pass
        return str(gdf.crs)

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------

    def _compute_measurements(
        self, gdf: gpd.GeoDataFrame
    ) -> list[dict[str, Any]]:
        """Compute area/length for every feature, returning a list of dicts."""
        source_crs_label = self._crs_label(gdf)
        measurement_crs = self._measurement_crs(gdf)
        measurement_crs_label = self._crs_label_from_crs(measurement_crs)

        need_transform = measurement_crs != gdf.crs
        projected = gdf.to_crs(measurement_crs) if need_transform else gdf

        results: list[dict[str, Any]] = []
        for idx in range(len(gdf)):
            geom = gdf.iloc[idx].geometry
            geom_type = geom.geom_type if geom is not None else "Unknown"

            base: dict[str, Any] = {
                "feature_id": idx,
                "geometry_type": geom_type,
                "source_crs": source_crs_label,
                "measurement_crs": measurement_crs_label,
            }

            if geom is None or geom.is_empty:
                results.append(
                    {
                        **base,
                        "measurement_type": None,
                        "value": None,
                        "unit": None,
                        "status": "NOT_MEASURABLE",
                        "reason": "Geometry is empty or null.",
                    }
                )
            elif geom_type in {"Polygon", "MultiPolygon"}:
                pgeom = projected.iloc[idx].geometry
                results.append(
                    {
                        **base,
                        "measurement_type": "area",
                        "value": round(float(pgeom.area), 4),
                        "unit": "m²",
                        "status": "MEASURED",
                        "reason": None,
                    }
                )
            elif geom_type in {"LineString", "MultiLineString"}:
                pgeom = projected.iloc[idx].geometry
                results.append(
                    {
                        **base,
                        "measurement_type": "length",
                        "value": round(float(pgeom.length), 4),
                        "unit": "m",
                        "status": "MEASURED",
                        "reason": None,
                    }
                )
            elif geom_type in {"Point", "MultiPoint"}:
                results.append(
                    {
                        **base,
                        "measurement_type": None,
                        "value": None,
                        "unit": None,
                        "status": "NOT_MEASURABLE",
                        "reason": f"Measurement is not applicable for {geom_type} geometry.",
                    }
                )
            else:
                results.append(
                    {
                        **base,
                        "measurement_type": None,
                        "value": None,
                        "unit": None,
                        "status": "UNSUPPORTED",
                        "reason": f"Unsupported geometry type: {geom_type}.",
                    }
                )

        return results

    @staticmethod
    def _crs_label_from_crs(crs) -> str | None:
        """Return a human-readable label for a pyproj CRS object."""
        if crs is None:
            return None
        try:
            epsg = crs.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
        except Exception:
            pass
        return str(crs)

    # ------------------------------------------------------------------
    # Feature serialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _serialise_value(value: Any) -> Any:
        """Convert a feature attribute value to a JSON-safe type."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        # Handle numpy scalars.
        try:
            if hasattr(value, "item"):
                return value.item()
        except Exception:
            pass
        return str(value)

    def _serialise_features(
        self, gdf: gpd.GeoDataFrame
    ) -> list[dict[str, Any]]:
        """Convert a GeoDataFrame to a list of JSON-safe feature dicts."""
        crs = self._crs_label(gdf)
        output: list[dict[str, Any]] = []
        for idx in range(len(gdf)):
            row = gdf.iloc[idx]
            geometry = row.geometry
            props = {
                str(k): self._serialise_value(v)
                for k, v in row.items()
                if k != gdf.geometry.name
            }
            output.append(
                {
                    "feature_id": idx,
                    "geometry_type": geometry.geom_type
                    if geometry is not None
                    else "Unknown",
                    "geometry": mapping(geometry)
                    if isinstance(geometry, BaseGeometry)
                    else None,
                    "crs": crs,
                    "properties": props,
                }
            )
        return output
