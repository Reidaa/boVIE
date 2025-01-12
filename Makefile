SHELL := /bin/sh

TARGET := bovie

REPOSITORY ?= reidaa
DOCKERFILE ?= Dockerfile
DOCKERTAG ?= latest

.PHONY: run lint format

fclean:
	rm -rf ids.txt

lint:
	ruff check

format:
	black ${TARGET}
	isort ${TARGET}
	ruff format

run:
	uv run ${TARGET}.py

pull:
	uv run python  ${TARGET}.py pull

bot:
	uv run python -O ${TARGET}.py bot


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
