"""Unit tests for the GeospatialService CRS and geometry handling."""

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

from app.services.geospatial_service import GeospatialService


def test_measurement_crs_is_projected_for_geographic_input(tmp_path):
    """Geographic CRS (EPSG:4326) should yield a projected measurement CRS."""
    repo_stub = type("R", (), {"root": str(tmp_path)})()
    service = GeospatialService(repository=repo_stub)
    gdf = gpd.GeoDataFrame(
        {"name": ["a"]},
        geometry=[Polygon([(77, 12), (77.01, 12), (77.01, 12.01), (77, 12.01)])],
        crs="EPSG:4326",
    )
    crs = service._measurement_crs(gdf)
    assert crs.is_projected


def test_measurement_crs_keeps_projected_input(tmp_path):
    """Already-projected CRS should be returned unchanged."""
    repo_stub = type("R", (), {"root": str(tmp_path)})()
    service = GeospatialService(repository=repo_stub)
    gdf = gpd.GeoDataFrame(
        {"name": ["a"]},
        geometry=[Polygon([(500000, 1430000), (500100, 1430000), (500100, 1430100), (500000, 1430100)])],
        crs="EPSG:32643",
    )
    crs = service._measurement_crs(gdf)
    assert crs == gdf.crs


def test_supported_geometry_types():
    """Verify that GeoDataFrame correctly identifies geometry types."""
    gdf = gpd.GeoDataFrame(
        {"name": ["poly", "line", "point"]},
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            LineString([(0, 0), (1, 0)]),
            Point(0, 0),
        ],
        crs="EPSG:4326",
    )
    assert list(gdf.geometry.geom_type) == ["Polygon", "LineString", "Point"]


def test_crs_label_returns_epsg_format(tmp_path):
    """CRS label should prefer EPSG:XXXX format."""
    repo_stub = type("R", (), {"root": str(tmp_path)})()
    service = GeospatialService(repository=repo_stub)
    gdf = gpd.GeoDataFrame(
        {"name": ["a"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    label = service._crs_label(gdf)
    assert label == "EPSG:4326"
