# DuckDocs: rules for Copilot (mandatory)

DuckDocs is a privacy-first local document Q&A app. FastAPI backend, Next.js frontend, PostgreSQL, ChromaDB and Ollama, all run by Docker Compose. The product promise is that nothing leaves the user's machine.

## Privacy
- No document content, question, answer, filename or embedding may be sent to any non-local host. No cloud LLM or embedding APIs, no hosted vector DBs, no analytics, no error-reporting SDKs.
- Telemetry stays off everywhere. `ANONYMIZED_TELEMETRY` must be "FALSE" on both the backend and chromadb services, and `NEXT_TELEMETRY_DISABLED` stays "1".
- No CDN fonts, scripts or images in the frontend. Self-host assets.
- Model weights, OCR models and Docker images may be downloaded at setup time only. Never lazily at runtime. If you add a model or dependency that downloads on first use, bake it into the image or mount it from `data/models` or `DUCKDOCS_OCR_MODEL_DIR`, and tell me.
- The "remote provider" feature stays opt-in and off by default. Any new provider base URL must be validated as localhost or a Docker-internal host unless an explicit opt-in setting is on.
- Never log document text or queries at INFO level or above beyond what already exists.

## Hardware
- Must run CPU-only on an 8 GB RAM laptop with Intel Iris graphics. Default models stay small (`llama3.2:1b` chat, `nomic-embed-text` embeddings).
- GPU support is optional, in a separate compose override file. Larger models are configuration, never defaults.
- Ask before adding any dependency that adds more than about 200 MB to an image (for example torch). Prefer the standard library, what is already installed, or ONNX Runtime.
- New heavy features go behind an env flag, default off, until the scorecard shows they help.

## Code changes
- Minimal, surgical diffs. No rewrites, renames or reformatting of untouched code.
- Keep the `/api/v1` request and response schemas backward compatible. The frontend (`frontend/lib/api/client.ts`) depends on them. Add fields, never remove or rename.
- Keep all existing tests passing. Add tests for every behaviour you add. Only edit an existing test if it is wrong, and explain why.
- Database or chunk-metadata changes need an Alembic migration and a re-ingest note.
- Never use `eval`, `exec` or shell execution on model output. Model output is untrusted input.

## Answer quality
- Never weaken the grounding gate. If evidence is missing or doesn't support the claim, refuse. A wrong cited answer is worse than a refusal.
- Never hard-code anything from the test fixtures (marker strings, file names, expected values). Fixes must be generic.
- Citations must be built from stored evidence by the app, never from text the model wrote. Every displayed quote must be verified as a substring or near-exact match of the cited evidence.

## Working style
- Windows PowerShell and Docker Desktop. `Select-String` has no `-Recurse`, so pipe from `Get-ChildItem -Recurse`.
- Run tests with: `docker compose cp backend/tests backend:/app/` then `docker compose exec -u root backend sh -c "pip install -q pytest && python -m pytest tests -q"`.
- Never delete or overwrite `data/`. For a clean run, move state to a new `data_backup_<n>` folder and tell me.
- Commit to the current feature branch only. Never push, merge, force-push or rebase unless I ask.
