PYTHON ?= python3
COMPOSE ?= docker compose

.PHONY: up down restart logs ps build test test-verbose install run

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up --build -d

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -q

test-verbose:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn app.main:app --reload
