.PHONY: all test lint up down test-backend test-frontend test-pipeline lint-backend lint-frontend lint-pipeline openapi check-openapi help

all: lint test

# -----------------------------------------------------------------------------
# Kiểm tra chất lượng (Quality Gates)
# -----------------------------------------------------------------------------

lint: lint-backend lint-frontend lint-pipeline

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check .

lint-frontend:
	cd frontend && npm run lint && npm run format:check && npm run typecheck

lint-pipeline:
	cd pipeline && uv run ruff check . && uv run ruff format --check .

test: test-backend test-frontend test-pipeline

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

test-pipeline:
	cd pipeline && uv run pytest -m "not model"

# -----------------------------------------------------------------------------
# Quản lý Docker Compose (BE-16)
# -----------------------------------------------------------------------------

up:
	docker compose up --build -d

down:
	docker compose down

# -----------------------------------------------------------------------------
# Hợp đồng REST API & OpenAPI
# -----------------------------------------------------------------------------

openapi:
	cd backend && uv run python scripts/generate_openapi.py

check-openapi:
	cd backend && uv run python scripts/generate_openapi.py --check
