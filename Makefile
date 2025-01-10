SHELL := /bin/sh

TARGET := pyvie.bot

REPOSITORY ?= reidaa
DOCKERFILE ?= Dockerfile
DOCKERTAG ?= latest

run:
	uv run pyvie_bot/

### Docker-related

docker:
		docker build -t ${REPOSITORY}/${TARGET}:${DOCKERTAG} -f ${DOCKERFILE} .
.PHONY: docker

docker-build-debug:
		docker build --progress=plain --no-cache -t ${REPOSITORY}/${TARGET}:debug -f ${DOCKERFILE} .
.PHONY: docker-build-debug

docker-run: docker
		docker run -p 8080:8080 ${REPOSITORY}/${TARGET}:${DOCKERTAG}
.PHONY: docker-run