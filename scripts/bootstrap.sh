#!/usr/bin/env sh
set -eu
mkdir -p data/documents data/db data/vectors data/models data/logs data/exports
[ -f .env ] || cp .env.example .env
docker compose up -d --build
printf '%s\n' 'DuckDocs is starting at http://localhost:3000'
