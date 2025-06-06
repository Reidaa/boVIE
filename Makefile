SHELL := /bin/sh

TARGET := bovie

REPOSITORY ?= reidaa
DOCKERFILE ?= Dockerfile
DOCKERTAG ?= latest

.PHONY: run lint format

fclean:
	rm -rf database.db

check:
	uv run mypy bovie.py

lint:
	uv run ruff check

format:
	black ${TARGET}.py src/
	isort ${TARGET}.py src/
	ruff format

fmt: format

run: check
	uv run ${TARGET}.py

pull: check
	uv run ${TARGET}.py

bot: check
	uv run ${TARGET}.py --continuous

help:
	uv run ${TARGET}.py --help

### Docker-related

docker:
		docker build -t ${REPOSITORY}/${TARGET}:${DOCKERTAG} -f ${DOCKERFILE} .
.PHONY: docker

docker-build-debug:
		docker build --progress=plain --no-cache -t ${REPOSITORY}/${TARGET}:debug -f ${DOCKERFILE} .
.PHONY: docker-build-debug

docker-run: docker
		docker run ${REPOSITORY}/${TARGET}:${DOCKERTAG}
.PHONY: docker-run
