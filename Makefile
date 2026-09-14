.PHONY: dev dev-down test lint fmt run-api demo build

# Full stack: postgres + redis + api + worker (+ OPA with --profile governance).
dev:
	docker compose up -d --build

dev-down:
	docker compose down

# Build images without starting.
build:
	docker compose build

test:
	pytest -q

lint:
	ruff check src apps tests
	ruff format --check src apps tests

fmt:
	ruff format src apps tests
	ruff check --fix src apps tests

# Run the API locally against SQLite (no Docker needed).
# Requires ACP_API_KEY + TENANT_DEFAULT in the environment or .env.
run-api:
	uvicorn acp.api:app --host 127.0.0.1 --port 8000 --reload \
		--app-dir src --env-file .env

# End-to-end logistics demo against a local API (expects the API up on :8000).
# Override: ACP_API_URL=http://localhost:8000 ACP_API_KEY=... make demo
demo:
	python examples/logistics-agent/demo.py
