SHELL := "/bin/sh"

TARGET := "bovie"

REPOSITORY := "reidaa"
DOCKERFILE := "Dockerfile"
DOCKERTAG := "latest"

PACKAGE := "bovie"

TURBO := "npx turbo run"

i:
	uv sync --all-packages
	npm install

upgrade:
	uv lock --upgrade
	uv sync --all-packages

fmt:
	{{TURBO}} format

lint:
	{{TURBO}} lint format:check

typecheck:
	{{TURBO}} check

test:
	{{TURBO}} test

cov:
	uv run --all-packages pytest --cov={{PACKAGE}} --cov-report=term-missing

cov-html:
	uv run --all-packages pytest --cov={{PACKAGE}} --cov-report=html
	xdg-open htmlcov/index.html || open htmlcov/index.html || true

check:
	{{TURBO}} lint format:check check test

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache .turbo htmlcov dist build apps/*/dist packages/*/dist

run:
	uv run --all-packages python -m {{PACKAGE}}.main

run-help:
	uv run --all-packages python -m {{PACKAGE}}.main --help

up:
	docker compose up -d --wait mysql nats

migrate owner="source":
	uv run --all-packages {{owner}}-migrate

build:
	{{TURBO}} build

verify-packages:
	{{TURBO}} verify:packages

workers:
	docker compose --profile workers up --build -d relay-bf relay-wttj receiver delivery

down:
	docker compose down

pre-commit:
	uv run --all-packages pre-commit run --all-files
