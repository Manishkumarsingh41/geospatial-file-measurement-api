"""Shared pytest fixtures for the geospatial API test suite."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon

# Use a temporary upload dir for tests so we never pollute production uploads.
_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="geo_test_uploads_")

os.environ["UPLOAD_DIR"] = _TEST_UPLOAD_DIR

from app.main import app  # noqa: E402  — must import after env override

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client():
    """Provide a fresh TestClient and clean up uploads between tests."""
    with TestClient(app) as c:
        yield c
    # Clean up any files created during the test.
    for child in Path(_TEST_UPLOAD_DIR).iterdir():
        if child.name != "index.json" and child.name != ".gitkeep":
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    # Reset the index.
    idx = Path(_TEST_UPLOAD_DIR) / "index.json"
    if idx.exists():
        idx.unlink(missing_ok=True)


# ------------------------------------------------------------------ #
# Programmatic fixture helpers (used when fixture files don't exist)  #
# ------------------------------------------------------------------ #


def make_kml_bytes(name: str, geometry_type: str, coords: str) -> bytes:
    """Build a minimal KML document with a single Placemark."""
    if geometry_type == "Point":
        geom_xml = f"<Point><coordinates>{coords}</coordinates></Point>"
    elif geometry_type == "LineString":
        geom_xml = f"<LineString><coordinates>{coords}</coordinates></LineString>"
    elif geometry_type == "Polygon":
        geom_xml = (
            f"<Polygon><outerBoundaryIs><LinearRing>"
            f"<coordinates>{coords}</coordinates>"
            f"</LinearRing></outerBoundaryIs></Polygon>"
        )
    else:
        geom_xml = ""

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2">'
        "<Document>"
        "<Placemark>"
        f"<name>{name}</name>"
        f"{geom_xml}"
        "</Placemark>"
        "</Document>"
        "</kml>"
    ).encode()


def make_shapefile_zip(geometry, crs: str = "EPSG:4326") -> bytes:
    """Create an in-memory ZIP containing a valid Shapefile set."""
    gdf = gpd.GeoDataFrame(
        {"name": ["test"]}, geometry=[geometry], crs=crs
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = Path(tmpdir) / "data.shp"
        gdf.to_file(shp_path, driver="ESRI Shapefile")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in Path(tmpdir).iterdir():
                zf.write(f, f.name)
        return buf.getvalue()


# ------------------------------------------------------------------ #
# Ready-made byte fixtures                                           #
# ------------------------------------------------------------------ #


@pytest.fixture()
def point_kml_bytes() -> bytes:
    """A KML file with a single Point near Bangalore."""
    path = FIXTURES_DIR / "point.kml"
    if path.exists():
        return path.read_bytes()
    return make_kml_bytes("Test Point", "Point", "77.5946,12.9716,0")


@pytest.fixture()
def polygon_kml_bytes() -> bytes:
    """A KML file with a single Polygon (~100 m square near Bangalore)."""
    path = FIXTURES_DIR / "polygon.kml"
    if path.exists():
        return path.read_bytes()
    return make_kml_bytes(
        "Test Polygon",
        "Polygon",
        "77.5946,12.9716,0 77.5956,12.9716,0 77.5956,12.9726,0 77.5946,12.9726,0 77.5946,12.9716,0",
    )


@pytest.fixture()
def linestring_kml_bytes() -> bytes:
    """A KML with a single LineString near Bangalore."""
    path = FIXTURES_DIR / "linestring.kml"
    if path.exists():
        return path.read_bytes()
    return make_kml_bytes(
        "Test Line",
        "LineString",
        "77.5946,12.9716,0 77.5956,12.9716,0",
    )


@pytest.fixture()
def mixed_kml_bytes() -> bytes:
    """A KML with Point, LineString, and Polygon placemarks."""
    path = FIXTURES_DIR / "mixed.kml"
    if path.exists():
        return path.read_bytes()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2">'
        "<Document>"
        "<Placemark><name>Pt</name>"
        "<Point><coordinates>77.5946,12.9716,0</coordinates></Point>"
        "</Placemark>"
        "<Placemark><name>Ln</name>"
        "<LineString><coordinates>77.5946,12.9716,0 77.5956,12.9716,0</coordinates></LineString>"
        "</Placemark>"
        "<Placemark><name>Pg</name>"
        "<Polygon><outerBoundaryIs><LinearRing>"
        "<coordinates>77.5946,12.9716,0 77.5956,12.9716,0 77.5956,12.9726,0 77.5946,12.9726,0 77.5946,12.9716,0</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon>"
        "</Placemark>"
        "</Document>"
        "</kml>"
    ).encode()


@pytest.fixture()
def polygon_shapefile_zip() -> bytes:
    """ZIP containing a Shapefile with a Polygon in EPSG:4326."""
    path = FIXTURES_DIR / "polygon_shapefile.zip"
    if path.exists():
        return path.read_bytes()
    poly = Polygon([
        (77.5946, 12.9716),
        (77.5956, 12.9716),
        (77.5956, 12.9726),
        (77.5946, 12.9726),
    ])
    return make_shapefile_zip(poly, "EPSG:4326")


@pytest.fixture()
def linestring_shapefile_zip() -> bytes:
    """ZIP containing a Shapefile with a LineString in EPSG:4326."""
    path = FIXTURES_DIR / "linestring_shapefile.zip"
    if path.exists():
        return path.read_bytes()
    line = LineString([(77.5946, 12.9716), (77.5956, 12.9716)])
    return make_shapefile_zip(line, "EPSG:4326")


@pytest.fixture()
def point_shapefile_zip() -> bytes:
    """ZIP containing a Shapefile with a Point in EPSG:4326."""
    path = FIXTURES_DIR / "point_shapefile.zip"
    if path.exists():
        return path.read_bytes()
    pt = Point(77.5946, 12.9716)
    return make_shapefile_zip(pt, "EPSG:4326")


@pytest.fixture()
def projected_shapefile_zip() -> bytes:
    """ZIP containing a Shapefile with a Polygon in EPSG:32643 (UTM 43N)."""
    path = FIXTURES_DIR / "projected_shapefile.zip"
    if path.exists():
        return path.read_bytes()
    poly = Polygon([
        (500000, 1430000),
        (500100, 1430000),
        (500100, 1430100),
        (500000, 1430100),
    ])
    return make_shapefile_zip(poly, "EPSG:32643")


@pytest.fixture()
def malformed_zip() -> bytes:
    """ZIP that does not contain any Shapefile components."""
    path = FIXTURES_DIR / "malformed.zip"
    if path.exists():
        return path.read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "not a shapefile")
    return buf.getvalue()


@pytest.fixture()
def corrupted_kml_bytes() -> bytes:
    """Bytes that are not valid KML/XML."""
    path = FIXTURES_DIR / "corrupted.kml"
    if path.exists():
        return path.read_bytes()
    return b"<<<THIS IS NOT VALID KML>>>"


@pytest.fixture()
def empty_kml_bytes() -> bytes:
    """Valid KML with no placemarks."""
    path = FIXTURES_DIR / "empty.kml"
    if path.exists():
        return path.read_bytes()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2">'
        "<Document><name>Empty</name></Document>"
        "</kml>"
    ).encode()


@pytest.fixture()
def zipslip_zip() -> bytes:
    """ZIP with a path-traversal entry."""
    path = FIXTURES_DIR / "zipslip.zip"
    if path.exists():
        return path.read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", "malicious content")
    return buf.getvalue()

