PYTHON ?= python
GO ?= go
COMPOSE := docker compose -f docker-compose.dev.yml
export PYTHONPATH := $(CURDIR)/parser:$(CURDIR)/panel:$(CURDIR)/warehouse:$(CURDIR)/backfill

.PHONY: dev-up dev-down migrate test fetch-local parse-file panel-dev

dev-up:
	$(COMPOSE) up -d
	@echo "Postgres: localhost:5432  user/pass/db=cpi"
	@echo "MinIO:    http://localhost:9000  console :9001  minioadmin/minioadmin"

dev-down:
	$(COMPOSE) down

migrate:
	$(PYTHON) warehouse/migrations/apply.py

test:
	cd fetcher && $(GO) test ./...
	$(PYTHON) -m pytest parser/tests panel/tests warehouse/tests -q

fetch-local:
	cd fetcher && $(GO) run ./cmd/cpifetch --config ../config/dev.yml --panel ../data/panel-dev.csv --once

panel-dev:
	$(PYTHON) panel/build_panel.py --version dev --sample 5000 --seed 42

parse-file:
	$(PYTHON) -m cpi_parser.cli parse --file $(FILE) --registry registry/agents.yml
