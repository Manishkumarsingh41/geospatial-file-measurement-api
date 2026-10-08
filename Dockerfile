FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install GDAL/GEOS/PROJ system libraries required by GeoPandas/Fiona.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gdal-bin libgdal-dev libgeos-dev libproj-dev proj-data proj-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY .env.example ./.env.example

RUN mkdir -p uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
