FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Tesseract runs OCR fully locally with no page cap, no API key, and no
# per-document quota -- see docs/22_OCR_PIPELINE.md. Language packs beyond
# English can be added here (e.g. tesseract-ocr-fra) as OCR_LANGUAGES grows.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home --uid 10001 duckdocs && mkdir -p /app/data && chown -R duckdocs:duckdocs /app
USER duckdocs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
