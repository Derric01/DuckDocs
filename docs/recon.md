# DuckDocs Phase 0 Recon

Date: 2026-10-10  
Branch: `abhidevv2`  
Scope: read-only code and documentation reconnaissance. This file is the only
workspace file added in Phase 0.

## Documentation precedence and conflicts

`.github/copilot-instructions.md` is mandatory. `CLAUDE.md`, `PRODUCT.md`, and
`DESIGN.md` are consistent with its privacy-first, evidence-aware product
direction except where the implementation or supporting documentation is more
specific:

| Topic | Conflict or drift | Precedence / implication |
|---|---|---|
| Default chat model | The Copilot instructions require the small `llama3.2:1b` default. `.env.example` uses it, but `backend/app/core/config.py` and the default values in `docker-compose.yml` use `gemma3:1b`. | Copilot instructions win. This is configuration drift to resolve in a later phase without changing the default chat model casually. |
| Telemetry | Copilot instructions require `ANONYMIZED_TELEMETRY="FALSE"` on both backend and ChromaDB. Compose sets it only on `chromadb`; backend has no equivalent environment setting. `CLAUDE.md` also notes Chroma telemetry errors as a current gotcha. | Copilot instructions win. Phase 8 must set it explicitly for both services and verify no telemetry path is enabled. |
| Runtime model downloads | Copilot instructions allow setup-time downloads only and prohibit lazy runtime downloads. `CLAUDE.md`/README describe optional PaddleOCR as downloading weights on first use, while `paddle.py` constructs Paddle lazily and falls back if weights are absent. | Copilot instructions win. PaddleOCR must remain optional and be pre-provisioned or documented as unavailable offline; RapidOCR is the compliant default. |
| Hardware target | The requested goal and Copilot instructions target CPU-only 8 GB laptops. `docs/04_NON_FUNCTIONAL_REQUIREMENTS.md` describes a 16 GB reference machine. | Copilot instructions and the current task win for this iteration; the 16 GB value is a reference, not the acceptance target. |
| OCR default wording | Older comments in `paddle.py` call PaddleOCR the default, but the registry and README select RapidOCR first in `auto`; RapidOCR bundles weights. | Runtime behavior and current README are authoritative; comments should be corrected only with a related change. |
| Provider privacy | `PRODUCT.md` and `CLAUDE.md` say local-first and no hidden calls, while the settings/API schema exposes cloud provider types and README says cloud providers are opt-in. The current registry does not actually implement cloud calls, but it accepts arbitrary provider configuration and labels them. | Copilot instructions win: remote providers stay opt-in, visibly labeled, and later must be local-URL validated unless explicitly permitted. |

## Code map

### Ask flow (`backend/app/services/rag.py`)

1. `RagService.ask(query, scope)` creates the response ID, calls
   `retrieve`, resolves the chat provider, and returns
   `GroundedResponse(outcome="insufficient_evidence")` immediately when no
   chunks are returned.
2. `RagService.retrieve` translates `SearchScope` into document IDs, queries
   `VectorStore.query`, and, when vector results exist, supplements them with
   repository keyword hits. The current hybrid score is:
   `vector_score + 0.15 * keyword_score`, capped at `1.0`, then sorted and
   truncated to `settings.top_k`. If vectors are unavailable it uses keyword
   retrieval, additionally requiring `_has_lexical_support`.
3. `build_ask_prompt` formats each retrieved unit as
   `[[chunk:<evidence-id>]] ... [[/chunk]]` and sends the exact prompt below.
4. `chat.generate(prompt, stream=False)` is called. Provider failure falls
   back to `ExtractiveChatAdapter`.
5. `GroundingGate.validate` parses `[chunk:<id>]` with `CITATION_RE`, rejects
   unknown IDs, requires citations for factual ask sentences, and calls
   `_claims_match_evidence` for lexical term and number support. It recognizes
   exactly `INSUFFICIENT_EVIDENCE` as a refusal.
6. If an Ollama result fails the gate, `RagService.ask` makes a second
   corrective Ollama call with a citation reminder. If that also fails, it
   invokes the extractive provider. This is the current fallback path that can
   turn weak model output into a grounded-looking response.
7. A final gate failure returns an explicit refusal with `refusal_reason` and
   diagnostic `top_score`/`threshold`.
8. `_bind_citations` maps cited IDs back to retrieved `Evidence`, selects a
   source passage with `select_evidence_passage`, and creates API citations.
   The displayed quote is therefore source-derived, but an empty selected
   passage is currently still emitted as a citation. `ask_stream_tokens`
   replays the already-computed answer; it does not stream provider generation.

Relevant thresholds and locations:

- `Settings.top_k` = 12, `min_similarity` = 0.35,
  `relevance_high_threshold` = 0.75, `relevance_medium_threshold` = 0.5 in
  `backend/app/core/config.py`.
- `VectorStore.query` drops vector scores below `min_similarity` and converts
  cosine distance to `1 - distance`.
- Keyword `_keyword_chunk` uses matched query terms divided by query-term
  count; the vector path only adds keyword hits at or above the medium
  relevance threshold. `_has_lexical_support` requires one match for a
  one-term query and two for a multi-term query.
- `GroundingGate` rejects when more than 60% of factual sentences are
  uncited, or when more than one non-stopword claim term is missing from the
  cited evidence. Number derivation allows sums of two or three evidence
  numbers.
- `select_evidence_passage` uses token overlap and sentence/clause candidates;
  it is not an exact or fuzzy quote verifier.

### Exact prompts and “Waymark”

The ask prompt is built in `build_ask_prompt`:

```text
You are DuckDocs Waymark. Answer ONLY from the provided context.
 cite every factual claim with [chunk:<id>] using only IDs present in the context.
Answer in one concise sentence unless the question explicitly asks for an aggregation or explanation.
If the context is insufficient, reply with exactly INSUFFICIENT_EVIDENCE.

Citation format example:
Question: What department does the record identify?
Answer: The record identifies the Engineering department. [chunk:ev_example]
Use the same [chunk:<id>] format with a real context ID in your answer.

Question: <query>

Context:
[[chunk:<evidence-id>]]
<evidence.snippet>
[[/chunk]]

Answer:
```

The actual implementation includes the exact capitalization and the
`Question:`/`Context:`/`Answer:` labels shown in
`backend/app/services/rag.py`; the indented “cite” line above is only
formatted to keep this code block readable. The string `Waymark` originates
from this system prompt. It is also the design-language name in
`docs/20_DESIGN_SYSTEM.md`, and a regression test intentionally uses the junk
output `I am DuckDocs Waymark.`.

The ingest-time abstractive summary prompt is built by
`build_summary_prompt` in `backend/app/services/summarize.py`:

```text
Summarize the following document in two or three sentences. Describe only what the document actually says; do not speculate or add outside context.

Title: <document name>

Document:
<up to 6000 characters of parsed page text>

Summary:
```

### API schemas

`SearchScope` in `backend/app/domain/models.py` has `type` (`library`,
`document`, or `selection`), optional `document_id`, and optional
`document_ids`. `GroundedResponse` has `id`, `kind`, `query`, `outcome`
(`grounded` or `insufficient_evidence`), nullable `answer`, `grounded`,
`citations`, `retrieved_chunk_count`, `provider`, `created_at`, optional
`refusal_reason`, and optional numeric `diagnostic`. `Citation` currently has
only `id`, `ordinal`, `evidence_unit_id`, and source-selected `snippet`.

### Evidence and stored metadata

`Evidence` is the stored evidence unit. It contains `id`, `document_id`,
`document_name`, generic `section`, `page`, `line_start`, `line_end`,
`snippet`, `retrieval_score`, `relevance`, `anchor_quality`, `fidelity_tier`,
optional `ocr_confidence`, optional `ocr_engine`, and optional normalized
`bbox`. It is persisted by either `repositories/memory.py` (JSON) or
`repositories/sql.py` (PostgreSQL). `ChunkCandidate` in
`services/chunking.py` carries page, line range, text, OCR confidence,
anchor quality, fidelity tier, and bbox. `ingest.py` selects `cell` anchors
for XLSX and `line` for structural documents; other documents use paragraph
anchors.

Current format provenance is encoded mostly in text and the generic page
field:

- PDF pages use native PDF page numbers (1-based); sparse pages are rasterized
  and OCR results are remapped from the scan subset back to their original
  page numbers before pages are reassembled in document order.
- Images use frame numbers as 1-based page numbers.
- DOCX uses page numbers created from explicit `w:br` elements with
  `w:type="page"`. Section breaks are not currently handled, and headers and
  footers are merged into the same page sequence.
- XLSX uses worksheet index as `page`, prefixes the text with `Sheet:
  <title>`, and flattens non-empty rows/cells. Sheet name and row identity are
  not separate metadata fields.
- PPTX uses slide index as `page`, prefixes text with `Slide <index>`, and
  includes text frames and table rows. Slide identity is not a separate field.
- CSV is flattened into pipe-delimited lines on one page; headers are not
  propagated as metadata to each row.
- YAML, JSON, and XML are currently handled by `parse_plain_text` as one
  page of decoded text; there is no key/element chunk model.
- HTML is converted to text by `_TextOnlyHTMLParser` on one page.

The chunker splits paragraphs, bounds oversized paragraphs by word windows,
groups them up to `chunk_max_words` with `chunk_overlap_words`, and caps the
document at `max_chunks_per_document`. Stored snippets are capped at 4000
characters by repository indexing.

### Provider registration and network behavior

`ProviderRegistry` loads `data/provider_configs.json`, otherwise creates
Ollama chat and embedding defaults plus extractive and keyword fallbacks.
Registered provider types include `ollama`, `openai`, `anthropic`, `gemini`,
`openai_compatible`, `extractive`, and `keyword`. Only Ollama adapters are
implemented in `_build`; cloud and OpenAI-compatible types resolve to an
extractive chat or keyword embedding adapter rather than making their own
remote calls. Ollama accepts a configurable `base_url` and uses
`urllib.request` for `/api/tags`, `/api/generate`, and `/api/embed`.
There is no remote-provider adapter yet, but settings accepts arbitrary
`base_url` values and connectivity testing invokes the resolved adapter.

### Parsing, chunking, and upload detection

Dispatch is `parse_upload(payload, suffix, settings, on_page)`:
PyMuPDF handles PDF, XML parsing handles DOCX, openpyxl handles XLSX,
python-pptx handles PPTX, Pillow plus the OCR registry handles images, the
CSV module handles CSV, the HTML parser handles HTML, and decoded plain text
handles code, JSON, XML, YAML, TXT, and Markdown. RapidOCR is the preferred
offline OCR engine; Tesseract is the fallback. PaddleOCR is optional and can
download weights lazily if selected without a local model directory.

Upload handling in `api/routers/documents.py` derives `suffix` solely from
`Path(file.filename).suffix`, checks it against `SUPPORTED_EXTENSIONS`, stores
the declared MIME type, and calls `probe_page_count` using that suffix.
There is no magic-byte/content detection. A ZIP-based XLSX renamed `.csv` is
therefore accepted as CSV, fails text parsing, and is later moved to review
with the generic extraction failure message.

### Vector and keyword score combination

Chroma stores one embedding per evidence unit and queries cosine distance.
`VectorStore.query` converts distance to a score in `[0, 1]` and filters by
`DUCKDOCS_MIN_SIMILARITY`. Repository keyword ranking sums `2` for a term in
the snippet and `1` for a term only in document name/section. When vectors
are available, the current combination is not reciprocal rank fusion: vector
hits are retained and qualifying keyword hits receive `keyword_score * 0.15`
added to their existing vector score. When vectors are unavailable, only
keyword results with `_has_lexical_support` survive.

## Privacy audit

The following are all observed outbound-call surfaces or setup-time network
surfaces found in the repository:

| Surface | File / line | Non-local destination or trigger | Configurable off/limited? |
|---|---|---|---|
| Ollama generation, embedding, and health | `backend/app/providers/ollama.py:47`, `:63`, `:115`, `:166` | Whatever `OLLAMA_BASE_URL` or provider config supplies; Compose defaults to Docker-internal `http://ollama:11434`, local development defaults to localhost. | Yes, by using extractive/keyword fallback or not configuring Ollama; arbitrary provider config URLs are not currently restricted. |
| Chroma HTTP client | `backend/app/services/vector_store.py:41-45` | `DUCKDOCS_CHROMA_URL`/`CHROMA_URL`; Compose uses `http://chromadb:8000`. | Yes, unset uses local persistent Chroma; arbitrary URL is accepted. |
| Ollama model pull | `docker-compose.yml:90-100` | `ollama pull` for missing configured models; registry is the Ollama service and the destination is whatever Ollama itself can reach. | Setup-time and conditional, not disabled by an offline preflight; pre-populate `data/models` to avoid it. |
| Python dependency/image downloads | `backend/Dockerfile:8-15`, `frontend/Dockerfile`, CI workflow | Debian apt repositories, PyPI, npm registry, and Docker registries during build/install. | Setup-time only; not runtime application calls. |
| RapidOCR model | `backend/app/services/ocr/rapid.py:42-64` and `backend/pyproject.toml` | Bundled in the wheel; no runtime fetch observed. | Yes: dependency baked at build time. |
| PaddleOCR model | `backend/app/services/ocr/paddle.py:80-122` | Paddle/Paddlex model downloads on first selected use if absent. | Only by not selecting Paddle or pre-populating its model directory; not fully offline-safe as currently documented. |
| Frontend Google fonts | `frontend/app/layout.tsx:2` | `next/font/google` fetches/builds Inter, JetBrains Mono, and Newsreader from Google during build. | Build-time only, but conflicts with the no-CDN/no-external-assets rule; not disabled at runtime. |
| Frontend API proxy | `frontend/app/api/v1/[...path]/route.ts:6,55` | Fetches the configured `DUCKDOCS_API_URL`; Compose uses backend-internal HTTP and local fallback uses loopback. | Yes, via configuration, but arbitrary URL can be supplied. |
| Health checks | `docker-compose.yml:20`, `:56`, `:124` | Loopback checks inside each container only. | Local-only. |
| CI dependency setup | `.github/workflows/ci.yml:17,26` | GitHub Actions runner reaches apt/PyPI. | CI-only, not a product runtime path. |

No analytics SDK, crash-reporting SDK, update checker, or document upload to a
cloud endpoint was found. `NEXT_TELEMETRY_DISABLED=1` is set in the frontend
container and Dockerfile. `ANONYMIZED_TELEMETRY=FALSE` is set for ChromaDB,
but not for backend. The frontend currently uses a Google font build surface,
which is the clearest violation of the strict no-CDN asset requirement.

## All observed configuration variables

Application and Compose variables currently observed:

`DUCKDOCS_FRONTEND_PORT`, `DUCKDOCS_API_PORT`, `DUCKDOCS_API_HOST`,
`DUCKDOCS_API_URL`, `DUCKDOCS_FRONTEND_ORIGIN`, `DUCKDOCS_DATA_ROOT`,
`DUCKDOCS_LOCAL_MODEL`, `DUCKDOCS_CHAT_MODEL`, `DUCKDOCS_EMBED_MODEL`,
`DUCKDOCS_POSTGRES_DB`, `DUCKDOCS_POSTGRES_USER`,
`DUCKDOCS_POSTGRES_PASSWORD`, `DUCKDOCS_DB_URL`, `DUCKDOCS_CHROMA_URL`,
`CHROMA_URL`, `OLLAMA_BASE_URL`, `DUCKDOCS_API_TOKEN`,
`DUCKDOCS_MAX_FILE_SIZE`, `DUCKDOCS_TOP_K`, `DUCKDOCS_MIN_SIMILARITY`,
`DUCKDOCS_RELEVANCE_HIGH_THRESHOLD`,
`DUCKDOCS_RELEVANCE_MEDIUM_THRESHOLD`,
`DUCKDOCS_SUMMARIZE_WITH_MODEL`, `DUCKDOCS_OCR_ENGINE`,
`DUCKDOCS_OCR_LANGUAGES`, `DUCKDOCS_OCR_MODEL_DIR`,
`DUCKDOCS_OCR_BATCH_SIZE`, `DUCKDOCS_OCR_DPI`,
`DUCKDOCS_OCR_MIN_CHARS_PER_PAGE`, `DUCKDOCS_CHUNK_MAX_WORDS`,
`DUCKDOCS_CHUNK_OVERLAP_WORDS`, `DUCKDOCS_MAX_CHUNKS_PER_DOCUMENT`,
`NEXT_TELEMETRY_DISABLED`, and `ANONYMIZED_TELEMETRY`.

`DUCKDOCS_API_URL` is consumed by the frontend proxy, while the backend
`Settings` class does not read it. `DUCKDOCS_MAX_FILE_SIZE`,
`DUCKDOCS_TOP_K`, and several thresholds are supported by code but omitted
from `.env.example`.

## Proposed phases 1–8

These are intentionally surgical and preserve the existing API shapes by
adding fields only:

1. **Baseline and scorecard fit:** inspect `scorecard.py`, verify the uploaded
   fixture set and real `GroundedResponse` parsing; touch only
   `scorecard.py` if its field mapping is wrong, and add `docs/scorecard-log.md`.
2. **Citation integrity:** update `backend/app/services/rag.py`,
   `backend/app/providers/ollama.py`/provider protocols as needed for
   structured output, extend `backend/app/domain/models.py` additively,
   add focused backend tests, and make the smallest corresponding changes in
   `frontend/lib/types.ts` and `frontend/components/workspace/citations.tsx`.
3. **Refusal calibration:** primarily `backend/app/services/rag.py` and
   `backend/app/domain/models.py`, with regression tests for lexical IDs,
   unsupported questions, and refusal reason codes.
4. **Retrieval:** `backend/app/services/rag.py`,
   `backend/app/services/vector_store.py`, repository search code, and
   parsing/metadata tests for generic page/slide/sheet/scanned hints. Any
   reranker must be separately justified and flag-gated before dependency
   changes.
5. **Structured data and file detection:** `backend/app/services/parsing.py`,
   `backend/app/services/chunking.py`, `backend/app/api/routers/documents.py`,
   the evidence/domain/repository metadata path, migration files if schema
   changes are required, and focused CSV/XLSX/YAML/JSON/XML/magic-byte tests.
6. **DOCX page awareness:** `backend/app/services/parsing.py` plus parser and
   citation tests for explicit page breaks and section breaks. Add a migration
   only if persisted metadata shape changes.
7. **Optional local provider flexibility:** provider protocol/registry and new
   adapter files, settings/API/frontend provider surfaces, Compose override(s),
   and README hardware guidance. Keep defaults unchanged and validate local
   base URLs.
8. **Privacy hardening and docs:** `docker-compose.yml`,
   `backend/app/core/config.py`, provider validation/settings, frontend
   layout/font assets, README, `docs/privacy.md` if created, and
   `docs/scorecard-log.md`. Add offline verification instructions and
   enforce strict-local defaults.

