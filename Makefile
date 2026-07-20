.PHONY: up down logs test lint build dev-backend dev-frontend

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

test:
	cd frontend && npm run typecheck
	cd backend && python -m pytest

lint:
	cd frontend && npm run typecheck
	cd backend && python -m ruff check app tests

build:
	cd frontend && npm run build

dev-backend:
	cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev
