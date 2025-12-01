SHELL := "/bin/sh"

TARGET := "bovie"

REPOSITORY := "reidaa"
DOCKERFILE := "Dockerfile"
DOCKERTAG := "latest"

PACKAGE := "bovie"

sync:
	uv sync

upgrade:
	uv lock --upgrade
	uv sync

lint:
	uv run ruff check src tests

lint-fix:
	uv run ruff check --fix src tests

typecheck:
	# uv run mypy src
	uv run ty check

test:
	uv run pytest

cov:
	uv run pytest --cov={{PACKAGE}} --cov-report=term-missing

cov-html:
	uv run pytest --cov={{PACKAGE}} --cov-report=html
	xdg-open htmlcov/index.html || open htmlcov/index.html || true

check: lint typecheck test

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf dist build

build:
	uv build

run:
	uv run python -m {{PACKAGE}}.main

run-help:
	uv run python -m {{PACKAGE}}.main --help

pull: typecheck
	uv run ${TARGET}.py

bot: typecheck
	uv run ${TARGET}.py --continuous

help:
	uv run ${TARGET}.py --help

up:
	docker compose up -d

down:
	docker compose down

### Docker-related

docker:
		docker build -t {{REPOSITORY}}/{{TARGET}}:{{DOCKERTAG}} -f {{DOCKERFILE}} .

docker-build-debug:
		docker build --progress=plain --no-cache -t {{REPOSITORY}}/{{TARGET}}:debug -f {{DOCKERFILE}} .

docker-run: docker
		docker run {{REPOSITORY}}/{{TARGET}}:{{DOCKERTAG}}
