# CURO — common commands (macOS / Linux / WSL / Git Bash).
# On Windows PowerShell use the same targets through ./dev.ps1, e.g.  ./dev.ps1 dev

ifeq ($(OS),Windows_NT)
  PY := .venv/Scripts/python.exe
  SYS_PY := python
else
  PY := .venv/bin/python
  SYS_PY := python3
endif
COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help env setup dev up down logs ps migrate seed learning api-types test test-api test-app lint \
        format app time extract screenshots compare clean-db local local-seed local-time

help: ## list targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

env: ## create .env from .env.example if it doesn't exist
	@test -f .env || (cp .env.example .env && echo "created .env")

setup: env ## install local tooling: Python venv (+ embedded test Postgres) and app packages
	$(SYS_PY) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -c api/constraints.txt -e "api[dev,localdb,tools]" -e worker
	cd app && npm install

up: env ## start db, redis, api, worker, scheduler in Docker and wait for /health
	$(COMPOSE) up -d --build
	$(SYS_PY) tools/wait_for_api.py

dev: up ## everything: Docker stack + Expo (scan the QR code with Expo Go)
	cd app && npx expo start

app: ## Expo only (stack already running)
	cd app && npx expo start

down: ## stop the stack (data is kept)
	$(COMPOSE) down

logs: ## follow api / worker / scheduler logs
	$(COMPOSE) logs -f api worker scheduler

ps: ## show container status
	$(COMPOSE) ps

migrate: ## apply database migrations
	$(COMPOSE) exec api python -m curo.db.migrate

seed: ## (re)load the demo creator @curo.demo: replays 14 days of mocked collection
	$(COMPOSE) exec api python -m curo.seed demo --reset

learning: ## what CURO has learned about an account, e.g. make learning ARGS=curo.demo
	$(COMPOSE) exec api python -m curo.learned $(ARGS)

api-types: ## regenerate the app's typed API client from the FastAPI schema
	$(PY) tools/gen_openapi.py
	cd app && npm run gen:api

time: ## move the clock, e.g. make time ARGS="advance 6h"
	$(COMPOSE) exec api python /repo/tools/timetravel.py $(ARGS)

test: test-api test-app ## run every test

test-api: ## Python tests (needs Docker's db or the embedded Postgres from `make setup`)
	cd api && ../$(PY) -m pytest

test-app: ## app type-check, lint and tests
	cd app && npm run typecheck && npm run lint && npm test

lint: ## lint + format check, Python and app
	$(PY) -m ruff check api worker tools
	$(PY) -m ruff format --check api worker tools
	cd app && npm run lint && npm run format:check

format: ## auto-format Python and app code
	$(PY) -m ruff check --fix api worker tools
	$(PY) -m ruff format api worker tools
	cd app && npm run format

extract: ## unpack the prototype into reference/prototype
	$(PY) tools/extract_prototype.py

screenshots: ## screenshot every prototype screen into reference/screens
	$(PY) tools/screenshot_prototype.py

compare: ## screenshot the app (needs `make seed` and `make app` running) and write reference/compare.html
	$(PY) tools/screenshot_app.py

clean-db: ## DESTRUCTIVE: stop the stack and delete the local database volume
	$(COMPOSE) down -v

# --- Without Docker: embedded Postgres + the worker as a thread (tools/local_stack.py) ---

local: env ## run API + worker + scheduler without Docker (ARGS=--seed loads the demo first)
	$(PY) tools/local_stack.py up $(ARGS)

local-seed: ## (re)load the demo creator into the no-Docker stack
	$(PY) tools/local_stack.py seed

local-time: ## move the no-Docker stack's clock, e.g. make local-time ARGS="advance 6h"
	REDIS_URL=redis://127.0.0.1:6390/0 $(PY) tools/timetravel.py $(ARGS)
