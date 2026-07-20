# DuckDocs implementation traceability

This table maps the first implementation slice to the source-of-truth specification. It is intentionally kept beside the numbered docs so a behavior change can be reviewed against its requirement before code changes merge.

| Requirement area | Source documents | Implementation | Verification |
| --- | --- | --- | --- |
| Local-first, no hidden telemetry, visible boundary | 01_VISION, 20_DESIGN_SYSTEM, 24_SECURITY, 25_PRIVACY | `frontend/components/shell/duckdocs-app.tsx` local-mode indicator and Settings privacy callout; `docker-compose.yml` has no telemetry service; `.env.example` excludes provider secrets | Frontend build; Compose config review |
| Four-surface information architecture | 07_FEATURE_SPECIFICATION, 17_FRONTEND_ARCHITECTURE, 18_UI_UX_SPECIFICATION | `frontend/app/{library,intelligence,review,settings}` and `components/shell/duckdocs-app.tsx` | `npm run typecheck`; `npm run build` |
| Persistent evidence interaction | 01_VISION, 03_FUNCTIONAL_REQUIREMENTS, 15_API_SPECIFICATION, 18_UI_UX_SPECIFICATION | `EvidencePane`, `CitationChip`, upload-created evidence records, `frontend/lib/api/client.ts`, `backend/app/repositories/memory.py` | Citation interaction in Intelligence and Library surfaces |
| Grounded answer/refusal contract | 03_FUNCTIONAL_REQUIREMENTS §7.2, 09_AI_ARCHITECTURE, 11_RAG_ARCHITECTURE, 33_ERROR_HANDLING | `backend/app/services/rag.py` Grounding Gate; `/api/v1/ask`, `/api/v1/ask/stream`; extractive fallback | `backend/tests/test_health.py`; typed `GroundedResponse` |
| Upload and observable ingestion | 07_FEATURE_SPECIFICATION, 10_DOCUMENT_PIPELINE, 15_API_SPECIFICATION, 21_FILE_PROCESSING | `LibrarySurface` dropzone; `/api/v1/documents`, `/api/v1/documents/{id}/status`, job SSE; DOCX/text extractors | Backend compile; upload validation and progress path |
| Provider adapter layer | 12_PROVIDER_ARCHITECTURE, 26_CONFIGURATION, 27_SETTINGS | `backend/app/providers/{base,ollama,extractive,keyword,registry,secrets}.py`; `/api/v1/settings/providers` CRUD + test | Adapter contract + settings CRUD tests |
| Vector retrieval with offline fallback | 11_RAG_ARCHITECTURE, 14_VECTOR_DATABASE | `backend/app/services/vector_store.py` (Chroma); keyword fallback in `RagService.retrieve` | Retrieval-fallback test |
| Optional PostgreSQL persistence | 13_DATABASE_DESIGN | `backend/app/repositories/sql.py` selected via `DUCKDOCS_DB_URL`; JSON repo default | Offline tests remain green without DB |
| Provider and health boundaries | 12_PROVIDER_ARCHITECTURE, 15_API_SPECIFICATION, 26_CONFIGURATION, 31_OBSERVABILITY | `/health`, `/ready`, `/api/v1/providers`, `/api/v1/settings`; live Settings Configure/Test UI | `docker compose config`; backend health test |
| Docker-first local topology | 08_SYSTEM_ARCHITECTURE, 29_DOCKER_ARCHITECTURE, 30_DEPLOYMENT | `docker-compose.yml` (Ollama/Chroma/Postgres env wiring), Dockerfiles, bootstrap scripts | `docker compose config`; `ollama pull` docs in README |
| Dense, accessible product language | 18_UI_UX_SPECIFICATION, 19_COMPONENT_LIBRARY, 20_DESIGN_SYSTEM, 36_CODING_STANDARDS | `DESIGN.md`, `frontend/app/globals.css`, typed React components, focus states, reduced-motion rules, dark/light and dense/comfortable modes | WCAG-oriented token review; typecheck/build |
