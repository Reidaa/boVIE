# BoVIE

BoVIE collects job offers across multiple sources and delivers new ones to Discord.
The project started as a VIE/VIA bot, which is where the name comes from, but it now
tracks general job offers of any contract type. Its collectors cover Welcome to the
Jungle, company career sites on Workday, and Business France VIE/VIA listings.

Go 1.27+, MySQL 8.4+, and NATS JetStream are required.

This repository is a single Go module (`github.com/Reidaa/boVIE`). pnpm installs the
Railway IaC SDK used by `.railway/railway.ts`.

| Directory | Contents | Toolchain |
| --- | --- | --- |
| `apps/` | Deployable Go services, one main package and Dockerfile each | Go |
| `packages/` | Shared Go libraries and schema migration CLIs | Go |
| `deploy/` | Broker and database configuration used by Compose and Railway | — |
| `.railway/` | Railway infrastructure as code (`railway.ts`) | pnpm |
| `tests/` | Frozen event contract fixtures, architecture, and integration tests | `go test` |

Each deployable service has its own command and multi-stage Dockerfile producing a
static binary. An app's directory, command, Docker image, Compose and Railway service,
and NATS account share one name. Its database uses the same name with underscores.
Services do not import other services. `tests/architecture_test.go` enforces package
boundaries and builds and checks every service binary independently.

| App in `apps/` | Responsibility | Database | NATS access |
| --- | --- | --- | --- |
| `collector-business-france` | Collect Business France VIE/VIA offers and publish the new ones | `collector_business_france` | Publish `offers.business_france.v1`; create `OFFERS` if missing |
| `collector-wttj` | Collect Welcome to the Jungle jobs and publish the new ones | `collector_wttj` | Publish `offers.wttj.v1`; create `OFFERS` if missing |
| `collector-workday` | Collect jobs from the configured Workday career sites and publish the new ones | `collector_workday` | Publish `offers.workday.v1`; create `OFFERS` if missing |
| `discord-intake` | Read offers from NATS and queue a Discord message for each new one | `discord` | Consume `OFFERS/discord-intake`; create it if missing |
| `discord-sender` | Post queued messages to the Discord webhook | `discord` | None |

Collectors run on schedules and publish new offers to NATS themselves. Each collector
receives only its own broker credentials. With Compose, it also receives only its own database
credentials. On Railway, all apps log in to MySQL as `root`; [ADR 0001](docs/adr/0001-service-based-services-with-one-offer-stream.md) explains why. `discord-intake` and
`discord-sender` run continuously.

A new broker needs no setup step. The first collector run creates the `OFFERS` stream.
`discord-intake` waits for the stream, then creates its own consumer. Afterwards,
`discord-intake` can update its own consumer but cannot delete it. No service can change
or delete the stream.

| Library in `packages/` | Contents |
| --- | --- |
| `offerevents` | The `OfferEvent` schema every app exchanges |
| `collectorstore` | Collector database schema, page recording, `collector-store-migrate` |
| `discordstore` | Discord database schema (inbox and queued messages), `discord-store-migrate` |
| `natsclient` | NATS connection, stream and consumer names, stream settings and creation, the collectors' publisher |
| `mysqlcommon` | MySQL connection pool, UTC timestamps, queue leases, SQL migration runner |
| `clicommon` | `.env` loading and log setup for app entrypoints |

Libraries never depend on an app. Each collector owns its offers and scan
checkpoints in its own database; the offers table records what it has already
published. `discord-intake` and `discord-sender` share the `discord` database.
With the Compose accounts, they cannot access collector databases. Collectors can run on different hosts.

[ADR 0001](docs/adr/0001-service-based-services-with-one-offer-stream.md) records why
the system uses coarse services that share one offer stream, and the rules for adding
sources and consumers. [ADR 0002](docs/adr/0002-offers-catalog-with-a-private-api.md)
records the planned offers catalog for the webapp; the [design doc](docs/offers-catalog.md)
has its pages, filters and build layers.

## Local setup

Install Go 1.27+, golangci-lint, Node.js, and pnpm (`mise install` provides all of them).

```sh
go mod download
pnpm install
cp .env.example .env
docker compose up -d --wait mysql nats
docker compose --profile workers build
docker compose --profile workers run --rm migrate-collector-business-france
docker compose --profile workers run --rm migrate-collector-wttj
docker compose --profile workers run --rm migrate-collector-workday
docker compose --profile workers run --rm migrate-discord
```

Compose provisions four databases with separate unprivileged accounts, persistent
MySQL/NATS volumes, and readiness checks. Its credentials are development examples;
ports bind to localhost. The initialization SQL runs only on a fresh MySQL volume.
Provision separate secrets and TLS for a production deployment. Do not reuse the
local credentials there.

Schema changes are explicit embedded SQL migrations tracked in `schema_migrations`
(and automatically bootstrapped from existing `alembic_version` tables when upgrading
an existing database). Startup does not create tables. To migrate an externally hosted database:

```sh
DATABASE_URL='mysql://user:password@host/collector_db' go run ./packages/collectorstore/cmd/collector-store-migrate
DATABASE_URL='mysql://user:password@host/discord' go run ./packages/discordstore/cmd/discord-store-migrate
```

Run `collector-store-migrate` separately for each collector database. Each database has its own
migration history. The migration creates the database when it is missing; the
database user then needs the right to create it. Percent-encode reserved characters in URL passwords.
Environment variables override `.env`.

## Collect offers

The default `.env` selects the Business France database and broker account.
Collectors need a running NATS broker. The first run creates the `OFFERS` stream:

```sh
go run ./apps/collector-business-france --limit 25 --country canada --specialization 'information systems'
DATABASE_URL='mysql://collector_wttj:local-collector-wttj-only@127.0.0.1/collector_wttj' NATS_USER=collector-wttj NATS_PASSWORD=local-nats-collector-wttj \
  go run ./apps/collector-wttj --query engineer --limit 50 --max-pages 5 --country CA
```

Business France accepts `--geozone`/`-g`, `--country`/`-c`,
`--specialization`/`-s`, `--limit`, and `--debug`. Filters are repeatable;
`BUSINESS_FRANCE_REGION`, `BUSINESS_FRANCE_COUNTRY`, `BUSINESS_FRANCE_SPECIALIZATION`, `BUSINESS_FRANCE_LIMIT`, and
`BUSINESS_FRANCE_DEBUG` also work. The limit bounds search results inspected per run.
The collector reads the public API key from the Business France offers page.
Set `BUSINESS_FRANCE_API_KEY` to use another key first. After a 401 response,
the collector reads the key from the page and retries once.

WTTJ accepts `WTTJ_QUERY`, `WTTJ_CONTRACTS`, `WTTJ_LIMIT`, and `WTTJ_MAX_PAGES`.
An empty query includes all titles. An empty contract filter accepts all contract types,
including types that WTTJ adds later. Only published jobs produce events.
Use repeated `--contract` options to select contract types. `WTTJ_CONTRACTS` accepts
space-separated values. `--country` accepts repeated ISO country codes.

```sh
DATABASE_URL='mysql://collector_wttj:local-collector-wttj-only@127.0.0.1/collector_wttj' NATS_USER=collector-wttj NATS_PASSWORD=local-nats-collector-wttj \
  go run ./apps/collector-wttj --contract full_time --contract internship --country CA
```

The collector searches the public v3 API, follows its pages, and fetches job details.
`--limit` counts inspected search results, including results excluded by filters.
WTTJ public search is not a complete feed of every job. Query and page limits still
bound each run, even without contract restrictions. See the [request contract](docs/wttj-api.md).

Workday reads its boards from `WORKDAY_BOARDS`, a JSON list. The variable is required:
the collector exits before it connects to MySQL or NATS when it is missing or empty.
In production, it is set on the Railway `collector-workday` service. Each board has its
public career site URL and company name. `searchText` and
`appliedFacets` are optional and go unchanged into Workday's job list request.
Empty values collect every job. `WORKDAY_LIMIT` (default 40) bounds the postings
inspected per board and run. The collector waits one second before each request.
A failed board does not stop the others, but it fails the run.

```sh
DATABASE_URL='mysql://collector_workday:local-collector-workday-only@127.0.0.1/collector_workday' NATS_USER=collector-workday NATS_PASSWORD=local-nats-collector-workday \
  go run ./apps/collector-workday \
  --boards '[{"url": "https://example.wd1.myworkdayjobs.com/Careers", "company": "Example", "searchText": "data"}]'
```

Read facet ids from the `facets` of a job list response. See the
[request contract](docs/workday-api.md).

The collectors are one-shot commands. Schedule them independently with cron or
your deployment scheduler. Support is limited to **one active collector per
source**. Database uniqueness handles duplicate discovery; it does not coordinate
source rate limits or overlapping scans. Multiple collectors require a renewable
run lease or explicit partitioning and shared rate limiting first.

For each page, a collector publishes its new offers and waits for every JetStream
acknowledgment. Only then does it commit the offers and checkpoint together. A
failed fetch or publish commits nothing, and the next run publishes those offers
again under the same event IDs. Restarts replay from the beginning because
offset/ranked results can move; already-recorded IDs are not published again.
Each recorded offer stores a hash of its normalized content and `last_seen_at`,
the last time a scan returned it. Collectors do not yet publish updates or closures.
Checkpoints describe completed progress, not a stable upstream cursor. Offers
that disappear or move outside the configured scan window cannot be guaranteed.

## Discord

With `DISCORD_WEBHOOK_URL` set, start the independent background processes:

```sh
docker compose --profile workers up -d discord-intake discord-sender
```

This starts posting to the configured real webhook. Collectors remain separate:

```sh
docker compose --profile workers run --rm collector-business-france
docker compose --profile workers run --rm collector-wttj
docker compose --profile workers run --rm collector-workday
```

Collectors outside Compose also need `NATS_URL`, `NATS_USER`, and `NATS_PASSWORD`
for their own broker account. For the background processes, set
`DATABASE_URL` and the broker variables for the relevant owner, then use:

```sh
go run ./apps/discord-intake
go run ./apps/discord-sender
```

`discord-sender` only needs `discord` database credentials and `DISCORD_WEBHOOK_URL`.
`--once` drains currently eligible work and exits; future retries still need another
invocation. Without it, these commands poll continuously. With `--once`, `discord-intake`
exits when the stream does not exist yet.

Services only create missing NATS objects. To change the stream's limits, an operator
uses the `nats-setup` administrator account, for example with the `nats` CLI in the
`natsio/nats-box` image:

```sh
docker run --rm --network host natsio/nats-box \
  nats --server nats://127.0.0.1:4222 --user nats-setup --password local-nats-setup \
  --inbox-prefix _INBOX.nats-setup stream edit OFFERS --max-bytes 2GiB --force
```

The account may only receive replies on `_INBOX.nats-setup.>`, so keep `--inbox-prefix`.
Then change `StreamConfig` in `packages/natsclient` to match, so new brokers get the same limits.

## Delivery and recovery

- An event has `version=1`, a `type` (`discovered`, `updated`, or `closed`), UUID
  `event_id`, `source`, case-sensitive string `source_offer_id`, aware UTC
  `observed_at`, and normalized display fields. Collectors only publish
  discoveries today, and only discoveries notify. Cross-board deduplication is not included.
- `event_id` is derived from the source, offer ID, and type (plus the content hash
  for updates). A republished event keeps its ID and `Nats-Msg-Id`. The Discord
  inbox drops it even after the broker's two-minute deduplication window.
- `discord-intake` commits its inbox and pending delivery in one transaction, then
  acknowledges NATS. Lost acknowledgments cause safe redelivery. Invalid events
  are logged without their payload and retried, so operators can investigate
  without silently discarding them. Each retry of a failing message waits twice
  as long as the previous one, from 30 seconds up to one hour. The log names the
  message's stream sequence and delivery count.
- A collector run fails when its scan has returned no results for 12 hours, or
  never has. A broken source usually returns an empty list instead of an error.
- `tests/contracts/offer_event_v1/` holds frozen published events. Every schema
  change must still parse them and derive the same event IDs; a change that cannot
  needs a new subject version. The test only checks that new code reads old
  events. `OfferEvent` rejects unknown top-level fields, so a new field also needs
  its consumers deployed before the collectors. Otherwise the old consumer retries
  the new events until it is updated.
- Delivery claims last 120 seconds. Transactions release locks before
  network calls; expired claims can be reclaimed. Completion and retry updates
  check the claim token and its unexpired lease. Database time governs leases.
- Failed work backs off from 10 seconds to one hour. HTTP delivery times out after
  15 seconds per network operation; NATS publish/ack waits are 10 seconds.
  A worker crash leaves pending work recoverable after its lease expires.
- Discord delivery is **at least once**. A crash after Discord accepts a message
  but before MySQL records success can cause a duplicate. Exactly-once external
  delivery is not guaranteed.
- The local `OFFERS` stream uses file storage and limits retention. Messages stay
  after consumers acknowledge them, so more consumers can be added and a new
  consumer can replay history. Messages expire after 90 days. The 1 GiB bound
  uses `DiscardNew`: when full, publishes fail, collectors record nothing, and the
  next run retries. The single local NATS server is not highly available;
  production resilience needs a managed/replicated deployment and tested backups.

Inspect `deliveries` in the `discord` database: `completed_at IS NULL` identifies pending work;
`attempts`, `available_at`, and `lease_until` show retry progress. Fix the failing
dependency and leave workers running. Do not manually mark messages delivered.
Use JetStream consumer statistics to inspect pending/redelivered messages.
Completed rows and inbox deduplication records are retained; plan storage and
retention before deleting history. Back up all databases and the broker volume.

## Deployment and validation

Railway production has one Railway MySQL server with a database per app, the focused services, private
connections, NATS storage, and collector schedules. `.railway/railway.ts` defines them as
Railway Infrastructure as Code. Railway deploys `main`. Railway creates a temporary copy for each pull request; copies do not post to Discord.
Use the [Railway deployment guide](docs/railway.md) for the initial deployment and updates.

Each service has a Dockerfile in its `apps/` directory. Docker builds use the repository
root as context, for example `docker build -f apps/collector-wttj/Dockerfile -t bovie-collector-wttj .`.
Each final image contains only that service's static binary and its schema migration binary.

```sh
just check
```

| Command | Check |
| --- | --- |
| `gofmt -l apps packages tests` | Formatting |
| `golangci-lint run ./...` | Linting |
| `go vet ./...` | Static analysis |
| `go test -race ./...` | Unit, contract, architecture, and integration tests |
| `go build ./...` | Build all packages and binaries |

To include integration tests, point these **test-only** variables at disposable
servers. The MySQL fixture creates and drops uniquely named test databases/users;
the NATS test creates and deletes its test stream. Never point them at production.

```sh
MYSQL_TEST_ADMIN_URL='mysql://root:test-password@127.0.0.1:33077/mysql' \
NATS_TEST_URL='nats://127.0.0.1:42277' go test -race ./...
```

Without these variables, integration tests report skips. CI supplies real
MySQL and NATS JetStream. Source HTTP and Discord are mocked; tests never send
real notifications. The suite covers deduplication, rollback, leases, cross-domain
database grants, lost acknowledgments, and end-to-end JetStream flows.

`NATS_AUTH_TEST_URL` enables the additional deployment-permissions test against a
separate disposable broker running `deploy/nats.conf` with its documented local
passwords. CI runs this check too.

Service boundaries and delivery guarantees are in [service ownership](docs/services.md).
