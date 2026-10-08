# Geospatial File Measurement API

A FastAPI-based service for processing geospatial files (KML and Shapefiles). It extracts features, handles coordinate reference systems (CRS), and calculates polygon areas and linestring lengths.

## Features

- Accepts `.kml` and `.zip` (Shapefile) uploads.
- Validates file structure and handles malformed data without crashing.
- Extracts geometries, properties, and CRS for all features.
- Automatically projects geographic CRS (like EPSG:4326) to a local UTM zone before measuring.
- Returns area in square meters (m²) and length in meters (m).
- Lightweight persistence (JSON-backed, no external DB needed for this setup).

## Requirements

- Python 3.11+
- GDAL/GEOS/PROJ libraries installed on the system (handled automatically if using Docker).

## Setup & Running Locally

1. **Environment setup:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Run the server:**
   ```bash
   uvicorn app.main:app --reload
   ```
   The API will be accessible at `http://127.0.0.1:8000`. You can test endpoints via the Swagger UI at `/docs`.

## Using Docker

To run the application inside a container (which handles the GDAL dependencies for you):

```bash
docker compose up --build
```

## API Usage

### 1. Upload a file
```bash
curl -X POST "http://localhost:8000/api/files/" -F "file=@my_data.kml"
```
Returns a file ID and summary.

### 2. View file details
```bash
curl http://localhost:8000/api/files/{id}/
```

### 3. Get measurements
```bash
curl http://localhost:8000/api/files/{id}/measurements/
```
Returns calculated areas and lengths for each feature.

## Testing

The project includes a full test suite using `pytest`.

```bash
pytest
```
To regenerate the test fixtures, run `python tests/create_fixtures.py`.
