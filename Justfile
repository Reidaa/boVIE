SHELL := "/bin/sh"

TARGET := "bovie"

REPOSITORY := "reidaa"
DOCKERFILE := "Dockerfile"
DOCKERTAG := "latest"

PACKAGE := "bovie"

i:
	uv sync --all-packages

upgrade:
	uv lock --upgrade
	uv sync --all-packages

fmt:
    uv run --all-packages ruff format
    uv run --all-packages ruff check --fix --extend-select=I

lint:
	uv run --all-packages ruff check services packages tests scripts

lint-fix:
	uv run --all-packages ruff check --fix services packages tests scripts

typecheck:
	uv run --all-packages ty check

test:
	uv run --all-packages pytest

cov:
	uv run --all-packages pytest --cov={{PACKAGE}} --cov-report=term-missing

cov-html:
	uv run --all-packages pytest --cov={{PACKAGE}} --cov-report=html
	xdg-open htmlcov/index.html || open htmlcov/index.html || true

check: lint typecheck test

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf dist build

run:
	uv run --all-packages python -m {{PACKAGE}}.main

run-help:
	uv run --all-packages python -m {{PACKAGE}}.main --help

up:
	docker compose up -d --wait mysql nats

migrate owner="source":
	uv run --all-packages {{owner}}-migrate

build:
	uv build --all-packages --out-dir dist/workspace

workers:
	docker compose --profile workers up --build -d relay-bf relay-wttj receiver delivery

down:
	docker compose down

pre-commit:
    uv run --all-packages pre-commit run --all-files
