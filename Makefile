# Developer commands for the Docker Compose stack. Run `make` or `make help`.
SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE ?= docker compose

# Make variables accepted on the command line:
#   make superuser EMAIL=ops@company.sa NAME="Ops"   (password is prompted for)
#   make flush FORCE=1                                (skip the confirmation prompt)
EMAIL ?=
NAME ?=
FORCE ?=

FLUSH_SQL := \
	"SET client_min_messages = warning;" \
	"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();" \
	"DROP SCHEMA IF EXISTS public CASCADE;" \
	"CREATE SCHEMA public AUTHORIZATION pg_database_owner;" \
	"GRANT USAGE ON SCHEMA public TO PUBLIC;"

.PHONY: help up down restart build logs ps migrate seed superuser flush fresh reset psql redis-cli backend-shell frontend-shell

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.env:
	cp .env.example .env
	@echo "Created .env from .env.example"

# --- Stack -----------------------------------------------------------------------

up: .env ## Build and start the whole stack in the background (frontend :5173, API :8000)
	$(COMPOSE) up -d --build --wait
	@echo ""
	@echo "  Frontend  http://localhost:$${FRONTEND_PORT:-5173}"
	@echo "  API docs  http://localhost:$${BACKEND_PORT:-8000}/api/docs"

down: ## Stop and remove the containers (data volumes are kept)
	$(COMPOSE) down

restart: ## Restart the backend and frontend
	$(COMPOSE) restart backend frontend

build: .env ## Rebuild the images (after dependency changes)
	$(COMPOSE) build

logs: ## Follow the logs (make logs s=backend for one service)
	$(COMPOSE) logs -f --tail=200 $(s)

ps: ## Show the containers
	$(COMPOSE) ps -a

# --- Database --------------------------------------------------------------------

migrate: .env ## Apply database migrations
	$(COMPOSE) run --rm migrate

seed: .env ## Load the demo data (mock payments only)
	$(COMPOSE) run --rm backend python -m app.cli seed-dev

superuser: .env ## Create a SUPER_ADMIN (prompts; or EMAIL=... NAME=...)
	@email='$(EMAIL)'; name='$(NAME)'; \
	if [ -z "$$email" ]; then read -r -p "Email: " email; fi; \
	if [ -z "$$email" ]; then echo "An email is required." >&2; exit 1; fi; \
	if [ -z "$$name" ]; then read -r -p "Full name [Administrator]: " name; fi; \
	name="$${name:-Administrator}"; \
	$(COMPOSE) run --rm -e ADMIN_PASSWORD backend \
		python -m app.cli create-admin --email "$$email" --name "$$name" --super

flush: .env ## Delete ALL data: drop the schema, re-apply migrations, clear Redis (FORCE=1 skips the prompt)
	@if [ "$(FORCE)" != "1" ]; then \
		read -r -p "This permanently deletes every row in the database and Redis. Type 'flush' to continue: " answer; \
		[ "$$answer" = "flush" ] || { echo "Aborted."; exit 1; }; \
	fi
	$(COMPOSE) up -d --wait postgres redis
	@was_running="$$($(COMPOSE) ps --status running --services | grep -xE 'backend|frontend' | tr '\n' ' ')"; \
	set -e; \
	$(COMPOSE) stop backend >/dev/null 2>&1 || true; \
	echo "Dropping schema public..."; \
	printf '%s\n' $(FLUSH_SQL) | $(COMPOSE) exec -T postgres \
		sh -c 'psql -v ON_ERROR_STOP=1 -q -o /dev/null -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'; \
	echo "Flushing Redis..."; \
	$(COMPOSE) exec -T redis redis-cli FLUSHALL >/dev/null; \
	echo "Re-applying migrations..."; \
	$(COMPOSE) run --rm migrate; \
	if [ -n "$${was_running// /}" ]; then $(COMPOSE) up -d --wait $$was_running; fi; \
	echo "Database flushed. Run 'make seed' for demo data or 'make superuser' for an admin."

fresh: ## Flush the database, then load the demo data
	$(MAKE) flush
	$(MAKE) seed

reset: ## Remove the containers AND every volume (database, Redis, uploads, node_modules)
	@read -r -p "This deletes all Docker volumes for this project. Type 'reset' to continue: " answer; \
	[ "$$answer" = "reset" ] || { echo "Aborted."; exit 1; }
	$(COMPOSE) down -v --remove-orphans

# --- Shells ----------------------------------------------------------------------

psql: ## Open psql in the database
	$(COMPOSE) exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

redis-cli: ## Open redis-cli
	$(COMPOSE) exec redis redis-cli

backend-shell: ## Open a shell in the backend container
	$(COMPOSE) exec backend bash

frontend-shell: ## Open a shell in the frontend container
	$(COMPOSE) exec frontend sh
