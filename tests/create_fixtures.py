"""Generate deterministic test fixture files for geospatial API testing."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon


def create_fixtures(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []

    # Coordinates near Bangalore, India (77.5946° E, 12.9716° N)
    # Roughly 100m is ~0.0009 degrees latitude/longitude
    lon_point = 77.5946
    lat_point = 12.9716
    poly_coords = [
        (77.5946, 12.9716),
        (77.5955, 12.9716),
        (77.5955, 12.9725),
        (77.5946, 12.9725),
        (77.5946, 12.9716),
    ]
    line_coords = [
        (77.5946, 12.9716),
        (77.5955, 12.9725),
    ]

    # Helper for shapefile zips
    def save_shapefile_zip(gdf: gpd.GeoDataFrame, zip_path: Path, base_name: str) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            shp_path = tmp_path / f"{base_name}.shp"
            gdf.to_file(shp_path, driver="ESRI Shapefile")

            # Ensure .cpg exists (some GDAL versions may not write it by default)
            cpg_path = tmp_path / f"{base_name}.cpg"
            if not cpg_path.exists():
                cpg_path.write_text("UTF-8\n", encoding="utf-8")

            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(tmp_path.iterdir()):
                    if file_path.is_file():
                        zf.write(file_path, arcname=file_path.name)
        created_files.append(zip_path)

    # 1. point.kml
    point_kml_path = output_dir / "point.kml"
    point_kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Point</name>
      <Point>
        <coordinates>77.5946,12.9716,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
    point_kml_path.write_text(point_kml_content, encoding="utf-8")
    created_files.append(point_kml_path)

    # 2. polygon.kml (~100m x 100m square near Bangalore)
    polygon_kml_path = output_dir / "polygon.kml"
    polygon_kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Polygon</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5946,12.9716,0
              77.5955,12.9716,0
              77.5955,12.9725,0
              77.5946,12.9725,0
              77.5946,12.9716,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""
    polygon_kml_path.write_text(polygon_kml_content, encoding="utf-8")
    created_files.append(polygon_kml_path)

    # 3. linestring.kml
    linestring_kml_path = output_dir / "linestring.kml"
    linestring_kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Line</name>
      <LineString>
        <coordinates>
          77.5946,12.9716,0
          77.5955,12.9725,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
    linestring_kml_path.write_text(linestring_kml_content, encoding="utf-8")
    created_files.append(linestring_kml_path)

    # 4. mixed.kml
    mixed_kml_path = output_dir / "mixed.kml"
    mixed_kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Point</name>
      <Point>
        <coordinates>77.5946,12.9716,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Test Line</name>
      <LineString>
        <coordinates>
          77.5946,12.9716,0
          77.5955,12.9725,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Test Polygon</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5946,12.9716,0
              77.5955,12.9716,0
              77.5955,12.9725,0
              77.5946,12.9725,0
              77.5946,12.9716,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""
    mixed_kml_path.write_text(mixed_kml_content, encoding="utf-8")
    created_files.append(mixed_kml_path)

    # 5. polygon_shapefile.zip
    polygon_gdf = gpd.GeoDataFrame(
        [{"name": "Test Polygon"}],
        geometry=[Polygon(poly_coords)],
        crs="EPSG:4326",
    )
    save_shapefile_zip(polygon_gdf, output_dir / "polygon_shapefile.zip", "polygon")

    # 6. linestring_shapefile.zip
    linestring_gdf = gpd.GeoDataFrame(
        [{"name": "Test Line"}],
        geometry=[LineString(line_coords)],
        crs="EPSG:4326",
    )
    save_shapefile_zip(linestring_gdf, output_dir / "linestring_shapefile.zip", "linestring")

    # 7. point_shapefile.zip
    point_gdf = gpd.GeoDataFrame(
        [{"name": "Test Point"}],
        geometry=[Point(lon_point, lat_point)],
        crs="EPSG:4326",
    )
    save_shapefile_zip(point_gdf, output_dir / "point_shapefile.zip", "point")

    # 8. projected_shapefile.zip (EPSG:32643 - UTM Zone 43N, 100m x 100m square in meters)
    projected_coords = [
        (500000.0, 1430000.0),
        (500100.0, 1430000.0),
        (500100.0, 1430100.0),
        (500000.0, 1430100.0),
        (500000.0, 1430000.0),
    ]
    projected_gdf = gpd.GeoDataFrame(
        [{"name": "Projected Polygon"}],
        geometry=[Polygon(projected_coords)],
        crs="EPSG:32643",
    )
    save_shapefile_zip(projected_gdf, output_dir / "projected_shapefile.zip", "projected")

    # 9. malformed.zip (no .shp file, just dummy .txt)
    malformed_path = output_dir / "malformed.zip"
    with zipfile.ZipFile(malformed_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dummy.txt", "This archive does not contain a shapefile.")
    created_files.append(malformed_path)

    # 10. corrupted.kml (invalid XML content)
    corrupted_path = output_dir / "corrupted.kml"
    corrupted_content = "<kml xmlns=\"http://www.opengis.net/kml/2.2\">\n<Document>\n<Placemark><name>Unclosed tag\n"
    corrupted_path.write_text(corrupted_content, encoding="utf-8")
    created_files.append(corrupted_path)

    # 11. empty.kml (valid KML with no features/placemarks)
    empty_path = output_dir / "empty.kml"
    empty_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Empty Document</name>
  </Document>
</kml>
"""
    empty_path.write_text(empty_content, encoding="utf-8")
    created_files.append(empty_path)

    # 12. zipslip.zip (path traversal entry ../../evil.txt)
    zipslip_path = output_dir / "zipslip.zip"
    with zipfile.ZipFile(zipslip_path, "w") as zf:
        zf.writestr("../../evil.txt", "evil content for path traversal test")
    created_files.append(zipslip_path)

    return created_files


if __name__ == "__main__":
    fixtures_path = Path(__file__).parent / "fixtures"
    files = create_fixtures(fixtures_path)
    print(f"Generated {len(files)} fixture files in {fixtures_path}:")
    for f in sorted(fixtures_path.iterdir()):
        print(f"  - {f.name} ({f.stat().st_size} bytes)")
