SHELL := "/bin/sh"

PACKAGE := "@bovie/collector-business-france"

TURBO := "pnpm exec turbo run"

i:
	pnpm install

upgrade:
	pnpm update --recursive

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
	rm -rf .turbo dist build apps/*/dist packages/*/dist

run:
	pnpm --filter {{PACKAGE}} exec bun run dist/cli.js

run-help:
	pnpm --filter {{PACKAGE}} exec bun run dist/cli.js --help

up:
	docker compose up -d --wait mysql nats

migrate store="collector-store":
	pnpm --filter @bovie/{{store}} exec bun run dist/cli.js

build:
	{{TURBO}} build

verify-packages:
	{{TURBO}} verify:packages

workers:
	docker compose --profile workers up --build -d discord-intake discord-sender

down:
	docker compose down

pre-commit:
	pre-commit run --all-files
