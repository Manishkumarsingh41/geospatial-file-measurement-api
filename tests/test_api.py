"""Comprehensive API-level tests for the Geospatial File Measurement API.

Every test exercises the real processing pipeline — no mocks are used for
geospatial logic.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient


# ================================================================== #
# 1. Health endpoint                                                  #
# ================================================================== #


class TestHealth:
    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ================================================================== #
# 2. KML uploads                                                      #
# ================================================================== #


class TestKMLUpload:
    def test_upload_point_kml(self, client: TestClient, point_kml_bytes: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("point.kml", point_kml_bytes, "application/vnd.google-earth.kml+xml")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert body["feature_count"] == 1
        assert body["filename"] == "point.kml"
        assert body["id"]
        assert body["crs"] is not None

    def test_upload_polygon_kml(self, client: TestClient, polygon_kml_bytes: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("polygon.kml", polygon_kml_bytes, "application/vnd.google-earth.kml+xml")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["feature_count"] == 1
        assert body["status"] == "COMPLETED"

    def test_upload_linestring_kml(self, client: TestClient, linestring_kml_bytes: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("linestring.kml", linestring_kml_bytes, "application/vnd.google-earth.kml+xml")},
        )
        assert resp.status_code == 201
        assert resp.json()["feature_count"] == 1

    def test_upload_mixed_kml(self, client: TestClient, mixed_kml_bytes: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("mixed.kml", mixed_kml_bytes, "application/vnd.google-earth.kml+xml")},
        )
        assert resp.status_code == 201
        assert resp.json()["feature_count"] == 3


# ================================================================== #
# 3. Shapefile ZIP uploads                                             #
# ================================================================== #


class TestShapefileUpload:
    def test_upload_polygon_shapefile(self, client: TestClient, polygon_shapefile_zip: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("polygon.zip", polygon_shapefile_zip, "application/zip")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert body["feature_count"] >= 1

    def test_upload_linestring_shapefile(self, client: TestClient, linestring_shapefile_zip: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("linestring.zip", linestring_shapefile_zip, "application/zip")},
        )
        assert resp.status_code == 201
        assert resp.json()["feature_count"] >= 1

    def test_upload_point_shapefile(self, client: TestClient, point_shapefile_zip: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("point.zip", point_shapefile_zip, "application/zip")},
        )
        assert resp.status_code == 201

    def test_upload_projected_shapefile(self, client: TestClient, projected_shapefile_zip: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("projected.zip", projected_shapefile_zip, "application/zip")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "COMPLETED"
        # Projected CRS should be reported.
        assert body["crs"] is not None


# ================================================================== #
# 4. Validation / error handling                                       #
# ================================================================== #


class TestValidation:
    def test_reject_unsupported_extension(self, client: TestClient):
        resp = client.post(
            "/api/files/",
            files={"file": ("data.csv", b"a,b,c\n1,2,3", "text/csv")},
        )
        assert resp.status_code == 400
        assert "unsupported" in resp.json()["detail"].lower() or "only" in resp.json()["detail"].lower()

    def test_reject_corrupted_kml(self, client: TestClient, corrupted_kml_bytes: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("corrupted.kml", corrupted_kml_bytes, "application/vnd.google-earth.kml+xml")},
        )
        assert resp.status_code == 400

    def test_reject_empty_kml(self, client: TestClient, empty_kml_bytes: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("empty.kml", empty_kml_bytes, "application/vnd.google-earth.kml+xml")},
        )
        assert resp.status_code == 400
        assert "no features" in resp.json()["detail"].lower()

    def test_reject_malformed_zip(self, client: TestClient, malformed_zip: bytes):
        resp = client.post(
            "/api/files/",
            files={"file": ("bad.zip", malformed_zip, "application/zip")},
        )
        assert resp.status_code == 400
        assert "shapefile" in resp.json()["detail"].lower() or "shp" in resp.json()["detail"].lower()

    def test_reject_zip_path_traversal(self, client: TestClient, zipslip_zip: bytes):
        # The ZIP contains ../../evil.txt — it must not contain .shp etc so validation
        # should reject it as an invalid shapefile archive before even extracting.
        resp = client.post(
            "/api/files/",
            files={"file": ("evil.zip", zipslip_zip, "application/zip")},
        )
        assert resp.status_code == 400

    def test_reject_non_zip_binary_as_zip(self, client: TestClient):
        resp = client.post(
            "/api/files/",
            files={"file": ("data.zip", b"NOT A ZIP FILE AT ALL", "application/zip")},
        )
        assert resp.status_code == 400
        assert "zip" in resp.json()["detail"].lower()

    def test_file_not_found(self, client: TestClient):
        resp = client.get("/api/files/nonexistent_id/")
        assert resp.status_code == 404

    def test_measurements_not_found(self, client: TestClient):
        resp = client.get("/api/files/nonexistent_id/measurements/")
        assert resp.status_code == 404


# ================================================================== #
# 5. File detail endpoint                                             #
# ================================================================== #


class TestFileDetail:
    def test_get_file_detail(self, client: TestClient, polygon_kml_bytes: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("polygon.kml", polygon_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == file_id
        assert body["feature_count"] == 1
        assert len(body["features"]) == 1
        feature = body["features"][0]
        assert feature["feature_id"] == 0
        assert feature["geometry_type"] == "Polygon"
        assert feature["geometry"] is not None
        assert "type" in feature["geometry"]
        assert "coordinates" in feature["geometry"]
        assert feature["crs"] is not None

    def test_file_detail_includes_properties(self, client: TestClient, polygon_kml_bytes: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("polygon.kml", polygon_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/")
        feature = resp.json()["features"][0]
        assert isinstance(feature["properties"], dict)


# ================================================================== #
# 6. Measurement endpoint                                             #
# ================================================================== #


class TestMeasurements:
    def test_polygon_area_measured(self, client: TestClient, polygon_kml_bytes: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("polygon.kml", polygon_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        assert resp.status_code == 200
        measurements = resp.json()
        assert len(measurements) == 1
        m = measurements[0]
        assert m["measurement_type"] == "area"
        assert m["unit"] == "m²"
        assert m["value"] > 0
        assert m["status"] == "MEASURED"
        assert m["source_crs"] is not None
        assert m["measurement_crs"] is not None

    def test_linestring_length_measured(self, client: TestClient, linestring_kml_bytes: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("linestring.kml", linestring_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        measurements = resp.json()
        assert len(measurements) == 1
        m = measurements[0]
        assert m["measurement_type"] == "length"
        assert m["unit"] == "m"
        assert m["value"] > 0
        assert m["status"] == "MEASURED"

    def test_point_not_measurable(self, client: TestClient, point_kml_bytes: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("point.kml", point_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        measurements = resp.json()
        assert len(measurements) == 1
        m = measurements[0]
        assert m["status"] == "NOT_MEASURABLE"
        assert m["value"] is None
        assert m["reason"] is not None

    def test_mixed_kml_measurements(self, client: TestClient, mixed_kml_bytes: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("mixed.kml", mixed_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        measurements = resp.json()
        assert len(measurements) == 3
        statuses = {m["geometry_type"]: m["status"] for m in measurements}
        # At least Polygon should be measured and Point not measurable.
        assert any(m["status"] == "MEASURED" for m in measurements)
        assert any(m["status"] == "NOT_MEASURABLE" for m in measurements)


# ================================================================== #
# 7. CRS handling                                                     #
# ================================================================== #


class TestCRS:
    def test_epsg4326_triggers_utm_projection(self, client: TestClient, polygon_kml_bytes: bytes):
        """EPSG:4326 input must be transformed to a projected CRS for measurement."""
        upload = client.post(
            "/api/files/",
            files={"file": ("polygon.kml", polygon_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        assert m["source_crs"] is not None
        assert m["measurement_crs"] is not None
        # The measurement CRS should be a UTM projection, not EPSG:4326.
        assert m["measurement_crs"] != "EPSG:4326"
        assert "EPSG:" in m["measurement_crs"]

    def test_projected_crs_used_directly(self, client: TestClient, projected_shapefile_zip: bytes):
        """A file already in a projected CRS should not be re-projected."""
        upload = client.post(
            "/api/files/",
            files={"file": ("projected.zip", projected_shapefile_zip)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        # Source and measurement CRS should be the same projected CRS.
        assert m["source_crs"] == m["measurement_crs"]
        assert m["status"] == "MEASURED"
        assert m["measurement_type"] == "area"

    def test_projected_polygon_area_correct(self, client: TestClient, projected_shapefile_zip: bytes):
        """A 100 m × 100 m square in EPSG:32643 should have area ≈ 10000 m²."""
        upload = client.post(
            "/api/files/",
            files={"file": ("projected.zip", projected_shapefile_zip)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        assert m["value"] == pytest.approx(10000.0, rel=0.01)

    def test_geographic_polygon_area_is_reasonable(self, client: TestClient, polygon_kml_bytes: bytes):
        """A ~111 m × ~111 m square at lat 12.97 should have area roughly 10 000–15 000 m²."""
        upload = client.post(
            "/api/files/",
            files={"file": ("polygon.kml", polygon_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        # 0.001 degree ≈ 111 m, so area ≈ 111*109 ≈ ~12000 m² (varies by latitude)
        assert 5_000 < m["value"] < 25_000

    def test_geographic_linestring_length_is_reasonable(self, client: TestClient, linestring_kml_bytes: bytes):
        """A 0.001-degree line at lat 12.97 should be roughly 100–120 m."""
        upload = client.post(
            "/api/files/",
            files={"file": ("linestring.kml", linestring_kml_bytes)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        assert 50 < m["value"] < 200


# ================================================================== #
# 8. Shapefile measurement tests                                       #
# ================================================================== #


class TestShapefileMeasurements:
    def test_shapefile_polygon_area(self, client: TestClient, polygon_shapefile_zip: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("polygon.zip", polygon_shapefile_zip)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        assert m["measurement_type"] == "area"
        assert m["value"] > 0

    def test_shapefile_linestring_length(self, client: TestClient, linestring_shapefile_zip: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("linestring.zip", linestring_shapefile_zip)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        assert m["measurement_type"] == "length"
        assert m["value"] > 0

    def test_shapefile_point_not_measurable(self, client: TestClient, point_shapefile_zip: bytes):
        upload = client.post(
            "/api/files/",
            files={"file": ("point.zip", point_shapefile_zip)},
        )
        file_id = upload.json()["id"]
        resp = client.get(f"/api/files/{file_id}/measurements/")
        m = resp.json()[0]
        assert m["status"] == "NOT_MEASURABLE"

