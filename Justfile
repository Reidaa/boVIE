SHELL := "/bin/sh"

PACKAGE := "collector_business_france"

TURBO := "pnpm exec turbo run"

i:
	uv sync --all-packages
	pnpm install

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

check:
	{{TURBO}} lint format:check check test

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache .turbo dist build apps/*/dist packages/*/dist

run:
	uv run --all-packages python -m {{PACKAGE}}.main

run-help:
	uv run --all-packages python -m {{PACKAGE}}.main --help

up:
	docker compose up -d --wait mysql nats

migrate store="collector-store":
	uv run --all-packages {{store}}-migrate

build:
	{{TURBO}} build

verify-packages:
	{{TURBO}} verify:packages

workers:
	docker compose --profile workers up --build -d discord-intake discord-sender

down:
	docker compose down

pre-commit:
	uv run --all-packages pre-commit run --all-files
