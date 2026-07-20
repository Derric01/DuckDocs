$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path data, data/documents, data/db, data/vectors, data/models, data/logs, data/exports | Out-Null
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
Write-Host 'DuckDocs is starting at http://localhost:3000'
