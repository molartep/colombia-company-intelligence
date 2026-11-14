.PHONY: up down install migrate backend frontend test test-db lint format build smoke refresh-parameters
up:
	docker compose up --build --wait --wait-timeout 120

down:
	docker compose down

install:
	python3.12 -m venv backend/.venv
	backend/.venv/bin/pip install -r backend/requirements-dev.lock
	backend/.venv/bin/pip install --no-deps -e backend
	cd frontend && npm ci

migrate:
	cd backend && .venv/bin/alembic upgrade head

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --no-access-log

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest
	cd frontend && npm test

test-db:
	docker compose --profile test up test-db -d --wait
	cd backend && TEST_DATABASE_URL=postgresql+asyncpg://cci:cci@localhost:5433/cci_test .venv/bin/pytest -m postgres

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
	cd frontend && npm run lint && npm run typecheck

format:
	cd backend && .venv/bin/ruff check . --fix && .venv/bin/ruff format .
	cd frontend && npm run format

build:
	cd frontend && npm run build
	backend/.venv/bin/pip wheel --no-deps ./backend -w /tmp/cci-wheels

smoke:
	backend/.venv/bin/python scripts/live_smoke.py

refresh-parameters:
	backend/.venv/bin/python scripts/refresh_parameters.py
