# DuckDocs

DuckDocs is a local-first, evidence-aware document intelligence workspace. It combines a dense library, grounded conversational search, review tooling, and explicit privacy controls in one product surface.

The implementation follows the source-of-truth specification in [`docs/`](docs/01_VISION.md), with the design register captured in [`PRODUCT.md`](PRODUCT.md) and [`DESIGN.md`](DESIGN.md).

## Run the interface

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` for the entry page, then continue into the workspace at `/intelligence`, `/library`, `/review`, or `/settings`. The workspace starts empty; upload your own files to create searchable local evidence.

## Run the API locally

OCR runs through a pluggable engine. **RapidOCR is the default**: the PP-OCR
models compiled to ONNX, with the weights shipped inside the wheel — no system
package, no first-run download, offline from the first document. **Tesseract**
is the fallback and needs its binary on `PATH`:

```powershell
# Debian/Ubuntu
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
# macOS
brew install tesseract
```

Select the engine with `DUCKDOCS_OCR_ENGINE=auto|rapidocr|paddleocr|tesseract`
(`auto` prefers RapidOCR and falls back rather than failing ingestion). The
upstream Paddle runtime is available as an extra — `pip install -e ".[paddle]"` —
for anyone who wants it instead of ONNX.

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API listens on `http://localhost:8000`. Without Ollama, Postgres, or Chroma running, DuckDocs stays on the offline path: JSON evidence index, keyword retrieval, and extractive grounded answers. Document parsing and OCR run either way -- they don't depend on Ollama/Postgres/Chroma being up.

Optional Make targets from the repo root:

```powershell
make dev-backend
make dev-frontend
```

## Run the local stack (recommended)

From the repo root:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Open `http://localhost:3000`. The API is on `http://localhost:8000`.

### Local models (one-time after first start)

Ollama starts empty. The chat and embedding models are **not** bundled; pull them once:

```powershell
docker compose exec ollama ollama pull gemma3:1b
docker compose exec ollama ollama pull nomic-embed-text
```

Until those pulls finish, DuckDocs still runs on the offline path (keyword search + extractive answers). After the pulls, Ollama chat/embeddings attach automatically when reachable.

Check what is installed:

```powershell
docker compose exec ollama ollama list
```

Health checks:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/ready`
- `GET http://localhost:8000/api/v1/openapi.json`

## Document ingestion & OCR

Uploads are parsed for real, not stubbed:

- **PDF** -- native text-layer extraction per page (PyMuPDF); pages with no or a sparse text layer fall back to OCR automatically.
- **Images** (PNG, JPG, WEBP, TIFF, BMP) -- always OCR'd, including multi-frame TIFF.
- **DOCX** -- paragraph/page-break-aware XML parsing. **XLSX** -- per-sheet, row/cell-aware. **PPTX** -- per-slide.
- **CSV, HTML, TXT/MD, JSON/XML/YAML, and source code** -- direct structured/text extraction.
- OCR runs on **every** page of a scanned document -- no page cap, no API key, no per-document quota. Scanned pages are recognized in batches (`DUCKDOCS_OCR_BATCH_SIZE`), so a long document amortizes model overhead instead of paying it per page.
- Confidence and bounding boxes are captured per page and never hidden: low-confidence OCR is labeled in the evidence inspector rather than silently blended in as if it were clean text.
- Every document and chunk carries an honest fidelity tier (`full_layout` / `structural` / `ocr_dependent`) so the UI never implies more precision than the parser actually delivered.
- Languages are configured with `DUCKDOCS_OCR_LANGUAGES` (engine-specific codes are mapped from the Tesseract-style names automatically).
- Every document is **summarized at ingest**, and the summary says how it was made: `extractive` is verbatim sentences from the document, `abstractive` is model output. Summarization never fails an ingest — extractive is the floor.
- If the API exits mid-ingest, the interrupted job is detected at the next startup, reported with an actionable message, and the document moves to `review`. The stored file is kept so `POST /api/v1/documents/{id}/retry` re-runs the pipeline.

## Product guarantees

- No analytics, telemetry, crash reporting, or hidden provider calls.
- Grounded responses contain citations; insufficient evidence is represented as a successful, explicit refusal state.
- Uploaded files and diagnostics stay under `data/` (and `backend/data/` when running the API from `backend/`), which is ignored by git.
- Cloud providers are opt-in and configured through the Settings surface.
- Local Ollama chat/embeddings, ChromaDB retrieval, and PostgreSQL persistence are optional and fall back safely when unavailable.
- OCR is 100% local -- scanned documents never leave the machine to be recognized.
- Answers stream token by token, but only the terminal result -- the one carrying citations -- is committed to the transcript. Stopping mid-stream says plainly that nothing was cited.

## Quality checks

```powershell
cd frontend
npm run typecheck
npm test
npm run build

cd ../backend
python -m pytest
python -m ruff check app tests migrations
python -m mypy app
```

## Database schema

The JSON repository is the default and needs nothing. When `DUCKDOCS_DB_URL` is
set, the schema is managed by Alembic and migrated to head automatically at
startup — including adopting a database created by an earlier build, which is
stamped at the baseline revision and then upgraded rather than rebuilt.

```powershell
cd backend
$env:DUCKDOCS_DB_URL="postgresql+psycopg://..."
alembic upgrade head          # what startup does for you
alembic revision -m "..."     # after changing a model in repositories/sql.py
```
