# BoVIE

Discover jobs from Welcome to the Jungle and VIE/VIA opportunities from
Business France, then deliver new offers to Discord. WTTJ accepts all contract
types by default. Python 3.13+, SQLAlchemy 2, MySQL 8.4, and NATS JetStream are required.

This repository is a [Turborepo](https://turborepo.dev) monorepo. Python code is a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) that Turborepo
reads natively (experimental `experimentalPythonWorkspaces`); TypeScript tooling is an
npm workspace. Both share one task graph and cache.

| Directory | Contents | Toolchain |
| --- | --- | --- |
| `apps/` | Deployable services, one package and Docker target each | uv |
| `packages/` | Shared Python libraries | uv |
| `infra/railway/` | Railway infrastructure as code | npm, TypeScript |
| `deploy/` | Broker and database configuration used by Compose and Railway | — |
| `tests/` | Cross-package Python test suite | pytest |

Each deployable service has its own package, dependencies, command, and Docker target.
The root contains development tools and one lockfile per toolchain (`uv.lock`,
`package-lock.json`). Services do not import other services. Tests enforce declared
imports and install each service independently.

| Directory in `apps/` | Command | Responsibility | Database | NATS access |
| --- | --- | --- | --- | --- |
| `business-france` | `bovie` | Collect and publish Business France offers | `business_france` | Publish `offers.business_france.v1` |
| `wttj` | `wttf` | Collect and publish WTTJ jobs | `wttj` | Publish `offers.wttj.v1` |
| `notification-intake` | `notification-intake` | Store incoming events and pending deliveries | `notifications` | Consume `OFFERS/notifications` |
| `discord-delivery` | `discord-delivery` | Send pending deliveries to Discord | `notifications` | None |
| `broker-setup` | `broker-setup` | Provision the stream and consumer | None | Administrator |

Collectors run on schedules and publish new offers to NATS themselves. Each collector
receives only its own database and broker credentials. Intake and delivery run
continuously. Broker setup runs once.

The libraries in `packages/` contain event contracts, source storage, notification
storage, database operations, broker connections, and process startup helpers.
They have no dependency on a deployable service. Source and notification storage
include separate migration commands and revision histories.

Each source owns its offers and scan checkpoints in a separate database. The
offers table is the collector's record of what it has already published.
Notification intake and Discord delivery share the notification database.
They cannot access source databases. Sources can run on different hosts.

## Local setup

Install Python 3.13+, uv, and Node.js 22.18+ (`mise install` provides all of them).

```sh
uv sync --all-packages
npm ci
cp .env.example .env
docker compose up -d --wait mysql nats
docker compose --profile workers build
docker compose --profile workers run --rm migrate-bf
docker compose --profile workers run --rm migrate-wttj
docker compose --profile workers run --rm migrate-notifications
docker compose --profile workers run --rm setup-nats
```

Compose provisions three databases with separate unprivileged accounts, persistent
MySQL/NATS volumes, and readiness checks. Its credentials are development examples;
ports bind to localhost. The initialization SQL runs only on a fresh MySQL volume.
Provision separate secrets and TLS for a production deployment. Do not reuse the
local credentials there. PyMySQL's `rsa` extra supports MySQL's default
`caching_sha2_password` authentication.

Schema changes are explicit Alembic migrations. Imports and collector startup do
not connect or create tables. To migrate an externally hosted database:

```sh
DATABASE_URL='mysql+pymysql://user:password@host/source_db' uv run --package bovie-source-store source-migrate
DATABASE_URL='mysql+pymysql://user:password@host/notification_db' uv run --package bovie-notification-store notification-migrate
```

Run `source-migrate` separately for each source. Each database has its own
Alembic version history. Migrations are included in the wheel. Percent-encode
reserved characters in URL passwords. Environment variables override `.env`;
each deployed process should receive only its own database credentials.

## Collect offers

The default `.env` selects the Business France database and broker account.
Collectors need a running NATS broker with the stream provisioned:

```sh
uv run --package bovie-business-france bovie --limit 25 --country canada --specialization 'information systems'
DATABASE_URL='mysql+pymysql://wttj:local-wttj-only@127.0.0.1/wttj' NATS_USER=wttj NATS_PASSWORD=local-nats-wttj \
  uv run --package bovie-wttj wttf --query engineer --limit 50 --max-pages 5 --country CA
```

Business France retains `--geozone`/`-g`, `--country`/`-c`,
`--specialization`/`-s`, `--limit`, and `--debug`. Filters are repeatable;
`BOVIE_REGION`, `BOVIE_COUNTRY`, `BOVIE_SPECIALIZATION`, `BOVIE_LIMIT`, and
`BOVIE_DEBUG` also work. The limit bounds search results inspected per run.

WTTJ accepts `WTTJ_QUERY`, `WTTJ_CONTRACTS`, `WTTJ_LIMIT`, and `WTTJ_MAX_PAGES`.
An empty query includes all titles. An empty contract filter accepts all contract types,
including types that WTTJ adds later. Only published jobs produce events.
Use repeated `--contract` options to select contract types. `WTTJ_CONTRACTS` accepts
space-separated values. `--country` accepts repeated ISO country codes.

```sh
DATABASE_URL='mysql+pymysql://wttj:local-wttj-only@127.0.0.1/wttj' NATS_USER=wttj NATS_PASSWORD=local-nats-wttj \
  uv run --package bovie-wttj wttf --contract full_time --contract internship --country CA
```

The collector searches the public v3 API, follows its pages, and fetches job details.
`--limit` counts inspected search results, including results excluded by filters.
WTTJ public search is not a complete feed of every job. Query and page limits still
bound each run, even without contract restrictions. See the [request contract](docs/wttj-api.md).

Both collectors are one-shot commands. Schedule them independently with cron or
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

## Notifications

With `DISCORD_WEBHOOK_URL` set, start the independent background processes:

```sh
docker compose --profile workers up -d receiver delivery
```

This starts delivery to the configured real webhook. Collectors remain separate:

```sh
docker compose --profile workers run --rm business-france
docker compose --profile workers run --rm wttj
```

Collectors outside Compose also need `NATS_URL`, `NATS_USER`, and `NATS_PASSWORD`
for their source's broker account. For the background processes, set
`DATABASE_URL` and the broker variables for the relevant owner, then use:

```sh
uv run --package bovie-notification-intake notification-intake
uv run --package bovie-discord-delivery discord-delivery
```

`discord-delivery` only needs notification database credentials and `DISCORD_WEBHOOK_URL`.
`--once` drains currently eligible work and exits; future retries still need another
invocation. Without it, these commands poll continuously. The `setup-nats` Compose job uses a
separate administrator account and must run before collectors or receivers.

The old collector `--webhook-url` option is removed. Terminal output records a
discovery; Discord delivery is acknowledged only by the notification worker.
There are no file-storage, bot/pull subcommands, or collector continuous-mode flags.

## Delivery and recovery

- An event has `version=1`, a `type` (`discovered`, `updated`, or `closed`), UUID
  `event_id`, `source`, case-sensitive string `source_offer_id`, aware UTC
  `observed_at`, and normalized display fields. Events without a `type` are
  discoveries. Collectors only publish discoveries today, and only discoveries
  notify. Cross-board deduplication is not included.
- `event_id` is derived from the source, offer ID, and type (plus the content hash
  for updates). A republished event keeps its ID and `Nats-Msg-Id`. The notification
  inbox drops it even after the broker's two-minute deduplication window.
- The receiver commits its inbox and pending delivery in one transaction, then
  acknowledges NATS. Lost acknowledgments cause safe redelivery. Invalid events
  are logged without their payload and retried, so operators can investigate
  without silently discarding them.
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

Inspect `deliveries` in the notification database: `completed_at IS NULL` identifies pending work;
`attempts`, `available_at`, and `lease_until` show retry progress. Fix the failing
dependency and leave workers running. Do not manually mark messages delivered.
Use JetStream consumer statistics to inspect pending/redelivered messages.
Completed rows and inbox deduplication records are retained; plan storage and
retention before deleting history. Back up all databases and the broker volume.

## Existing Postgres data

This change does not transfer or delete an existing Postgres database or volume.
Before a live cutover, decide whether offer history must be retained. Alembic
creates the MySQL schema; it does not transfer records between database engines.

If legacy history is required, an explicit, tested export/import must precede
collection against MySQL. Import distinct legacy offer IDs as seen offers without
payloads or events. Legacy rows cannot prove Discord delivery because the
old writer ordering could record terminal success before Discord failed. Keep
the original database for reconciliation. No legacy importer is run automatically.
Do not use `docker compose down -v` on an existing deployment.

## Deployment and validation

Railway staging is defined in `infra/railway/railway.ts`. It creates three Railway MySQL
databases, the focused services, private connections, NATS storage, and collector schedules.
Use the [Railway deployment guide](docs/railway.md) for the initial deployment and updates.
Discord delivery starts without a source connection until you configure a staging webhook.

Docker builds use the repository root as context. Select the service directory name
as the target, for example `docker build --target wttj -t bovie-wttj .`.
Each final image contains only that service and its installed dependencies.
The default Docker target remains Business France.

The old `bovie-worker` and `bovie-migrate DOMAIN` commands are removed.
Replace them with the commands above when updating an existing deployment.
Existing MySQL tables, Alembic revision IDs, and version-1 events remain compatible.
Remove `WTTJ_QUERY=VIE` from an existing environment to enable the broader default.
Collection can create more notifications once non-VIE offers enter the scan window.

### Upgrading from the outbox relay

Earlier releases wrote events to a source `outbox` table, and an `outbox-relay`
service published them to a work-queue stream. To upgrade an existing deployment:

1. Stop the collectors. Let each relay publish its remaining outbox events, or run
   the previous release's `outbox-relay --source SOURCE --once`.
2. Let notification intake drain the `OFFERS` stream, then stop the relays.
3. Deploy this release. `source-migrate` refuses to drop an outbox that still has
   unpublished events. `broker-setup` replaces the empty work-queue stream with a
   limits-retention stream and refuses if the old stream still holds messages.
   Both checks first block new writes (by renaming the outbox, or detaching the
   stream from the offer subjects), so a process still running from the previous
   release fails and retries instead of losing an event. On a refusal, the outbox
   or stream is restored; drain it and deploy again.
4. Give each collector its source's `NATS_URL`, `NATS_USER`, and `NATS_PASSWORD`.
   The broker accounts and permissions are unchanged.

```sh
npx turbo run lint format:check check test verify:packages
```

| Task | Python (`bovie-python` root and members) | TypeScript (`bovie-railway`) |
| --- | --- | --- |
| `lint` | Ruff check | Oxlint |
| `format`, `format:check` | Ruff format | Oxfmt |
| `check` | ty | `tsc --noEmit` |
| `test` | pytest over `tests/` | Node test runner |
| `build` | `uv build` into each member's `dist/` | — |
| `verify:packages` | Installs each app's wheel alone with `scripts/check_packages.py` | — |

Use `--filter`, for example `npx turbo run build --filter=bovie-wttj`, to run one package
and its dependencies. The `Justfile` recipes call the same tasks.

To include integration tests, point these **test-only** variables at disposable
servers. The MySQL fixture creates and drops uniquely named test databases/users;
the NATS test creates and deletes its test stream. Never point them at production.

```sh
MYSQL_TEST_ADMIN_URL='mysql+pymysql://root:test-password@127.0.0.1:33077/mysql' \
NATS_TEST_URL='nats://127.0.0.1:42277' npx turbo run test
```

Without these variables, integration tests report skips. CI supplies real
MySQL 8.4 and NATS JetStream. Source HTTP and Discord are mocked; tests never send
real notifications. The suite covers deduplication, rollback, leases, cross-domain
database grants, lost acknowledgments, and both complete source flows.

`NATS_AUTH_TEST_URL` enables the additional deployment-permissions test against a
separate disposable broker running `deploy/nats.conf` with its documented local
passwords. CI runs this check too.

Implementation details and remaining deployment decisions are in the
[handover notes](docs/handoff.md).
