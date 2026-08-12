# CLAUDE.md

Working notes for this codebase. Read this before making changes.

## What DuckDocs is

A local-first, evidence-aware document intelligence workspace. Upload documents,
ask questions in natural language, and get answers where **every claim carries a
citation back to the exact passage**. When the evidence isn't there, the product
refuses rather than guessing.

The non-negotiable product rule: **honesty about provenance and uncertainty**.
OCR confidence, fidelity tiers, and refusals are surfaced, never hidden.

## Commands

```bash
# Backend  (Python 3.12+ required)
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000

python -m pytest -q          # 55 tests
python -m ruff check app tests
python -m mypy app           # strict mode, must stay clean

# Frontend
cd frontend
npm install
npm run dev                  # :3000
npm run typecheck            # must stay clean
npm run build

# Full stack
docker compose up -d --build
```

**Running tests locally:** set `DUCKDOCS_OCR_ENGINE=tesseract` to skip PaddleOCR's
weight-download attempt, which is slow when the model host is unreachable.

## Architecture

```
backend/app/
  main.py              FastAPI app + all routes (~570 lines; split if it grows much more)
  core/config.py       Settings.from_env() — every tunable is an env var
  core/errors.py       DuckDocsError + the stable error envelope
  domain/models.py     Pydantic models = the API contract
  providers/           Chat/embedding adapters (ollama, extractive, keyword) + registry
  repositories/        memory.py (JSON) and sql.py (Postgres); same interface.
                       `AnyRepository` in __init__.py is the type both satisfy.
  services/
    parsing.py         Format dispatch -> ParsedDocument (pages + provenance)
    chunking.py        ParsedDocument -> ChunkCandidate (page-aware, overlap)
    ocr/               Pluggable OCR engines (see below)
    preview.py         On-demand page rasterization for the preview UI
    summarize.py       Ingest-time document summary (extractive, model optional)
    rag.py             Retrieval + grounding gate + citation binding
    vector_store.py    Chroma wrapper, degrades to keyword search

frontend/                Tailwind + shadcn-style components on Radix
  app/                 Thin routes; one per surface + landing
  app/globals.css      Theme variables (HSL triples) + a few component classes
  tailwind.config.ts   THE design system: palette, type scale, radii, motion
  lib/utils.ts         cn() — clsx + tailwind-merge
  components/ui/       Primitives (button.tsx, primitives.tsx, toast.tsx)
  components/workspace/
    workspace-provider.tsx   Shared state for every surface
    app-shell.tsx            Sidebar + topbar + panel orchestration
    surfaces/                One file per surface
  lib/api/client.ts    All backend calls + API->UI mapping
  lib/theme.ts         Theme/density persistence + pre-paint bootstrap
```

### The ingestion pipeline

```
upload -> parse (per page) -> [OCR fallback if no text layer]
       -> chunk -> summarize -> embed -> index
```

Parsing happens in a background task via `asyncio.to_thread` — it is CPU-bound and
must never block the event loop. Progress is reported per stage to the ingest job,
which the frontend polls while anything is processing.

### OCR (`services/ocr/`)

Engines sit behind the `OcrEngine` protocol so the backend is swappable:

- **PaddleOCR** — default. Better on poor scans and non-Latin scripts, returns
  per-line polygons which become real bounding-box citation anchors.
  Downloads weights once on first use, then fully offline.
- **Tesseract** — fallback. Its language data ships with the OS package, so it
  works on a machine that has never had network access.

`DUCKDOCS_OCR_ENGINE=auto|paddleocr|tesseract`. `auto` prefers Paddle and falls
back rather than failing ingestion.

Scanned pages are recognized in **batches** (`DUCKDOCS_OCR_BATCH_SIZE`), not one
call per page — this is what makes long scanned documents tolerable. Every page
of a scanned document is processed; there is no page cap.

## Invariants — don't break these

1. **Never claim more precision than the parser delivered.** `fidelity_tier`
   (`full_layout` / `structural` / `ocr_dependent` / `best_effort`) and
   `anchor_quality` (`line` / `paragraph` / `cell` / `bbox`) are stored data, not
   UI guesses. An OCR chunk only gets `bbox` anchor quality if it actually has a box.
2. **Low OCR confidence is labeled, never hidden or filtered out.** Averaging must
   include low-confidence units.
3. **A document must never read `ready` if a required stage failed.** Use `review`.
4. **No hidden network calls.** Remote providers are opt-in and visibly labeled.
5. **Insufficient evidence is a successful, explicit refusal** — HTTP 200 with
   `outcome: "insufficient_evidence"`, not an error.
6. **Bounding boxes are normalized** (0–1, top-left origin) so they stay valid at
   any render DPI.
7. **A summary states how it was made.** `extractive` is verbatim document
   sentences; `abstractive` is model output. The UI labels which, because they
   warrant different levels of trust. Summarization never fails an ingest — the
   extractive result is the floor when a model is absent or errors.

## Conventions

- Comments explain *why*, not *what*. Prefer no comment to a restatement of the code.
- Backend: strict mypy, ruff (line length 120). Third-party stubs are declared in
  `pyproject.toml` overrides.
- Frontend: Tailwind utilities only — no CSS-in-JS, no new semantic class names.
  Colours come from the theme (`bg-card`, `text-muted-foreground`), never raw
  hex or `bg-[#...]`; a hardcoded colour is a bug. Add a variable in
  `globals.css` and map it in `tailwind.config.ts` instead.
- The visual language is Apple/iOS: grouped inset lists on a tinted canvas,
  systemBlue as the only accent, larger radii, layered soft shadows,
  translucent chrome (`.material`), and the `ease-spring` curve for motion.
- Components follow the shadcn pattern (Radix primitive + CVA variants + `cn`),
  authored in-repo rather than installed, so they can be edited freely.
- Every interactive element needs hover / focus-visible / disabled states and an
  accessible name.
- Tests exercise real code paths (real Tesseract, real PyMuPDF). PaddleOCR is
  tested against a stubbed reader because its weights can't be assumed present.

## Current state

Working: ingestion for PDF/DOCX/XLSX/PPTX/images/CSV/HTML/text/code, local OCR
with confidence + bboxes, keyword and vector retrieval, grounding gate with
citation binding, page-image preview endpoint, full UI across 4 surfaces + landing.

**Known gaps** (deliberate, not oversights):
- Legacy DOC/PPT/XLS (needs LibreOffice conversion in the worker)
- OCR deskew/denoise (needs OpenCV; only grayscale + autocontrast today)
- Table-structure OCR for scanned tables
- OCR language auto-detection
- `main.py` is approaching the size where it should split into routers
- No frontend test suite

## Gotchas

- `Settings` is frozen and read once at import. Tests construct their own
  `Settings(...)` and override the FastAPI dependency rather than mutating env.
- The OCR engine registry **memoizes loaded models**. Call `reset_engine_cache()`
  in tests that patch availability.
- `next/font/google` needs network at build time (it self-hosts afterwards).
- Chroma prints telemetry errors on startup; harmless, unrelated to our code.
- PaddleOCR pulls a heavy transitive tree via `paddlex` (langchain, openai,
  pandas). Unused at runtime, but it inflates the image — worth revisiting.
