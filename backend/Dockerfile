FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# OCR runs fully locally with no page cap, API key, or per-document quota
# (docs/22_OCR_PIPELINE.md). PaddleOCR is the default engine; Tesseract stays
# installed as the offline fallback because its language data ships with the
# OS package and needs no download. libgl1/libglib are OpenCV runtime deps
# pulled in by PaddleOCR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Warm the PaddleOCR weights at build time so the first upload in a fresh
# container does not stall on a download -- and so the running container
# needs no network for OCR at all. Non-fatal: if the model host is
# unreachable during build, the engine falls back to Tesseract at runtime.
ENV DUCKDOCS_OCR_MODEL_HOME=/app/.paddleocr
RUN python -c "\
from paddleocr import PaddleOCR;\
PaddleOCR(lang='en', use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)\
" || echo 'PaddleOCR weights not prefetched; runtime will fall back to Tesseract.'
RUN useradd --create-home --uid 10001 duckdocs && mkdir -p /app/data && chown -R duckdocs:duckdocs /app
USER duckdocs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
