# Privacy and network access

DuckDocs stores documents, derived evidence, and vectors in the local Compose
volumes. The default Compose topology connects only the frontend, backend,
Postgres, Ollama, ChromaDB, and the Ollama model initializer. Chroma telemetry
is disabled both in its service environment and in the Python client settings.
The frontend's Google fonts are fetched by `next/font/google` during image
build and are served from the frontend image at runtime; the browser does not
request fonts, scripts, or images from a CDN.

## Outbound-call audit

This inventory covers application HTTP clients, frontend proxying, model and
dependency acquisition, and container networking. File locations and line
numbers refer to this Phase 8 revision.

| Location | Non-local destination or trigger | Can configuration disable it? |
|---|---|---|
| `backend/app/providers/ollama.py:65,86,132,183` | Chat generation, provider health checks, and embeddings. Requests use the provider's configured `base_url`. | Yes. Strict local mode rejects remote provider URLs and remote provider types; use the local Ollama service or the extractive/keyword fallbacks. |
| `backend/app/api/routers/settings.py:106-115` | A user can register or test a provider endpoint. In strict local mode, cloud provider types and non-local URLs are rejected. | Yes. Set `DUCKDOCS_STRICT_LOCAL=false` to expose remote-provider setup. Do so only when remote processing is intended. |
| `frontend/app/api/v1/[...path]/route.ts:6,55` | Browser API requests are proxied to `DUCKDOCS_API_URL`; Compose points this at `http://backend:8000/api/v1`. | Yes. Set it to the local API. The shipped Compose value is Docker-internal. |
| `backend/app/services/vector_store.py:39-60` | If `DUCKDOCS_CHROMA_URL` or `CHROMA_URL` is set, the backend connects to that Chroma URL; otherwise it uses a local persistent client. | Yes. Leave both variables unset for embedded local storage, or point `DUCKDOCS_CHROMA_URL` at the Compose `chromadb` service. |
| `docker-compose.yml:111-116` | `ollama-model-init` runs `ollama pull` when either configured model is absent from the local Ollama volume. This contacts the Ollama model registry through Ollama. | Yes after setup: keep both models in `./data/models` and use the offline Compose overlay below. On a first setup, model acquisition requires network access. |
| `backend/Dockerfile:11-17` | `apt-get` and `pip install` contact package repositories while building the backend image. | Yes at runtime; build the image before disconnecting. Rebuilds need package caches or network access. |
| `frontend/Dockerfile:4,13` | `npm install` and `next build` run during image construction. `next/font/google` may fetch font files during that build. | Yes at runtime; build the image before disconnecting. The generated fonts are served by the app. |
| `docker-compose.yml` image declarations (`postgres`, `ollama`, `chromadb`) | Docker pulls images when they are not already present locally. | Yes after setup: pre-pull the images. A fresh install needs registry access. |
| `docker-compose.yml:126-133` and `backend/app/services/vector_store.py:39-51` | Chroma service/client telemetry. Both set anonymized telemetry off. The pinned client still logs a PostHog capture signature error even though sending is disabled; see the verification note below. | Disabled in the shipped configuration; there is no application setting to enable it. |
| `backend/app/services/ocr/rapid.py:44-79` | RapidOCR loads model files bundled in `rapidocr-onnxruntime`; it performs local inference. | No network call to disable. The packaged weights are available after image build. |
| `backend/app/services/ocr/paddle.py:75-112` | Optional PaddleOCR loads only pre-existing `det/` and `rec/` weights below `DUCKDOCS_OCR_MODEL_DIR`. Missing weights make the engine unavailable; it does not download them. | No runtime network call. Mount prepared weights or use the bundled RapidOCR default. |
| `frontend/app/layout.tsx:2-4` | `next/font/google` fetches fonts during `next build`, then the generated assets are served by Next.js. | Build time only; remove this import and use local CSS fonts to disable the build fetch. It is not a browser runtime request. |
| `scorecard.py:31-52` | The optional scorecard client calls its configured API URL; default is `http://localhost:8000`. | Yes. Run against localhost, or do not run the scorecard. |

No other application source contains external HTTP destinations, CDN asset
references, or runtime download code in the frontend, backend, or Compose
configuration reviewed for this phase. Docker bridge networks normally permit
egress; an offline run must use the internal-network overlay below.

## Verify it runs offline

Prepare the machine once while connected: build the frontend and backend images,
pull the Postgres, Ollama, and ChromaDB images, and let `ollama-model-init`
finish downloading the configured chat and embedding models. Keep the models in
the mounted `./data/models` volume. If using PaddleOCR, prepare local inference
weights first and place `det/` and `rec/` under the host directory configured by
`DUCKDOCS_OCR_MODEL_DIR` (default `./data/ocr-models`). PaddleOCR will stay
unavailable rather than downloading missing files. RapidOCR needs no separate
download because its weights ship in the backend dependency.

For an isolated-container check, stop the stack and start it with the offline
overlay:

```powershell
docker compose down
docker compose -f docker-compose.yml -f docker-compose.offline.yml up -d
docker compose -f docker-compose.yml -f docker-compose.offline.yml ps
```

The overlay marks the shared bridge `internal: true`, so services can reach
each other but have no external route. Confirm the effective network:

```powershell
$network = docker network ls --filter label=com.docker.compose.network=duckdocs_internal --format '{{.Name}}'
docker network inspect $network --format '{{.Internal}}'
docker compose -f docker-compose.yml -f docker-compose.offline.yml ps
```

The first command must print `true`; verify the Compose services are healthy.
For an active egress check from the backend, a connection to a public numeric
address must fail while internal service traffic continues to work:

```powershell
docker compose -f docker-compose.yml -f docker-compose.offline.yml exec -T backend python -c "import socket; socket.create_connection(('1.1.1.1', 443), timeout=3)"
docker compose -f docker-compose.yml -f docker-compose.offline.yml exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://chromadb:8000/api/v1/heartbeat').status)"
```

The socket command is expected to fail with a network-unreachable error. The
Chroma request is expected to return `200`. On Docker Desktop for Windows, this
internal-only overlay did not publish the frontend/API ports to the Windows
host during Phase 8 verification, so use it to verify isolation and internal
health rather than for a browser demo. For a UI demo with Wi-Fi off, use the
normal Compose network and disable the host's internet connection before
starting the stack; this keeps the published localhost ports available while
the host has no outside route. With existing models,
document upload, parsing, bundled RapidOCR, indexing, search, grounded Q&A,
citations, and the local Ollama model work offline. A missing Ollama model makes
`ollama-model-init` fail rather than fetch it; temporarily restore networking,
run the normal Compose setup so the initializer can pull the configured models,
then restart with the offline overlay. Image and dependency builds likewise
must be completed before disconnecting.

To check the telemetry regression in Docker logs after this rollout, run:

```powershell
docker compose -f docker-compose.yml -f docker-compose.offline.yml logs backend chromadb
```

The Chroma `posthog` error `capture() takes 1 positional argument` may still
appear. On the Phase 8 image it did: Chroma 0.5.23 sets `posthog.disabled=True`
when anonymized telemetry is false, but still calls the three-argument
`posthog.capture` shim. The installed PostHog API rejects that signature and
Chroma logs the exception. Since the shim is disabled, no telemetry is sent;
the error is a compatibility/logging defect, not a successful outbound event.
