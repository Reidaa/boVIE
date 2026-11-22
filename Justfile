SHELL := "/bin/sh"

APP := "collector-business-france"

i:
	go mod download
	pnpm install

fmt:
	gofmt -w apps packages tests

lint:
	test -z "$(gofmt -l apps packages tests)"
	golangci-lint run ./...

vet:
	go vet ./...

test:
	go test -race ./...

check: lint vet test build

clean:
	rm -rf bin dist

run:
	go run ./apps/{{APP}}

run-help:
	go run ./apps/{{APP}} --help

up:
	docker compose up -d --wait mysql nats

migrate store="collectorstore":
	go run ./packages/{{store}}/cmd/{{ if store == "collectorstore" { "collector-store-migrate" } else { "discord-store-migrate" } }}

build:
	go build ./...

workers:
	docker compose --profile workers up --build -d discord-intake discord-sender

down:
	docker compose down
