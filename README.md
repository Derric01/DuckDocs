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

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API listens on `http://localhost:8000`. Without Ollama, Postgres, or Chroma running, DuckDocs stays on the offline path: JSON evidence index, keyword retrieval, and extractive grounded answers.

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

## Product guarantees

- No analytics, telemetry, crash reporting, or hidden provider calls.
- Grounded responses contain citations; insufficient evidence is represented as a successful, explicit refusal state.
- Uploaded files and diagnostics stay under `data/` (and `backend/data/` when running the API from `backend/`), which is ignored by git.
- Cloud providers are opt-in and configured through the Settings surface.
- Local Ollama chat/embeddings, ChromaDB retrieval, and PostgreSQL persistence are optional and fall back safely when unavailable.

## Quality checks

```powershell
cd frontend
npm run typecheck
npm run build

cd ../backend
python -m pytest
python -m ruff check app tests
```
