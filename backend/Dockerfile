FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# OCR runs fully locally with no page cap, API key, or per-document quota
# (docs/22_OCR_PIPELINE.md). RapidOCR is the default engine and ships its
# weights inside the wheel, so the image needs no model download at build or
# run time. Tesseract stays installed as the fallback. libgl1/libglib are
# OpenCV runtime deps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Migrations run from the app at startup, so the revision files and their
# config have to be in the image.
COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --create-home --uid 10001 duckdocs && mkdir -p /app/data && chown -R duckdocs:duckdocs /app
USER duckdocs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
