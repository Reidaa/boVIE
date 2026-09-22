# BoVIE

Discover jobs from Welcome to the Jungle and VIE/VIA opportunities from
Business France, then deliver new offers to Discord. WTTJ accepts all contract
types by default. Python 3.13+, SQLAlchemy 2, MySQL 8.4, and NATS JetStream are required.

This repository is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/).
Each deployable service has its own package, dependencies, command, and Docker target.
The root contains development tools and one shared lockfile. Services do not import
other services. Tests enforce declared imports and install each service independently.

| Directory in `services/` | Command | Responsibility | Database | NATS access |
| --- | --- | --- | --- | --- |
| `business-france` | `bovie` | Collect Business France offers | `business_france` | None |
| `wttj` | `wttf` | Collect WTTJ jobs | `wttj` | None |
| `outbox-relay` | `outbox-relay --source SOURCE` | Publish committed events | One source | Publish its source subject |
| `notification-intake` | `notification-intake` | Store incoming events and pending deliveries | `notifications` | Consume `OFFERS/notifications` |
| `discord-delivery` | `discord-delivery` | Send pending deliveries to Discord | `notifications` | None |
| `broker-setup` | `broker-setup` | Provision the stream and consumer | None | Administrator |

Run one relay deployment per source. The relay performs the same operation for each
source and receives only that source's credentials. Collectors run on schedules.
The relay, intake, and delivery services run continuously. Broker setup runs once.

The libraries in `packages/` contain event contracts, source storage, notification
storage, database operations, broker connections, and process startup helpers.
They have no dependency on a deployable service. Source and notification storage
include separate migration commands and revision histories.

Each source owns its offers, scan checkpoints, and outbox in a separate database.
An outbox stores events until the relay receives a broker acknowledgment.
Notification intake and Discord delivery share the notification database.
They cannot access source databases. Sources can run on different hosts.

## Local setup

```sh
uv sync --all-packages
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

The default `.env` selects the Business France database:

```sh
uv run --package bovie-business-france bovie --limit 25 --country canada --specialization 'information systems'
DATABASE_URL='mysql+pymysql://wttj:local-wttj-only@127.0.0.1/wttj' uv run --package bovie-wttj wttf --query engineer --limit 50 --max-pages 5 --country CA
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
DATABASE_URL='mysql+pymysql://wttj:local-wttj-only@127.0.0.1/wttj' \
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

Each completed page commits its new offers, outbox events, and checkpoint
together. A failed page commits none of them. Restarts replay from the beginning
because offset/ranked results can move; already-seen IDs suppress duplicate events.
Checkpoints describe completed progress, not a stable upstream cursor. Offers
that disappear or move outside the configured scan window cannot be guaranteed.

## Relay and notifications

With `DISCORD_WEBHOOK_URL` set, start the independent background processes:

```sh
docker compose --profile workers up -d relay-bf relay-wttj receiver delivery
```

This starts delivery to the configured real webhook. Collectors remain separate:

```sh
docker compose --profile workers run --rm business-france
docker compose --profile workers run --rm wttj
```

For processes outside Compose, set `DATABASE_URL`, `NATS_URL`, `NATS_USER`, and
`NATS_PASSWORD` for the relevant owner, then use:

```sh
uv run --package bovie-outbox-relay outbox-relay --source business_france
uv run --package bovie-outbox-relay outbox-relay --source wttj
uv run --package bovie-notification-intake notification-intake
uv run --package bovie-discord-delivery discord-delivery
```

`discord-delivery` only needs notification database credentials and `DISCORD_WEBHOOK_URL`.
`--once` drains currently eligible work and exits; future retries still need another
invocation. Without it, these commands poll continuously. The `setup-nats` Compose job uses a
separate administrator account and must run before relays or receivers.

The old collector `--webhook-url` option is removed. Terminal output records a
discovery; Discord delivery is acknowledged only by the notification worker.
There are no file-storage, bot/pull subcommands, or collector continuous-mode flags.

## Delivery and recovery

- An event has `version=1`, UUID `event_id`, `source`, case-sensitive string
  `source_offer_id`, aware UTC `observed_at`, and normalized display fields.
  Only discoveries notify. Updates and cross-board deduplication are not included.
- A source marks its outbox entry complete only after JetStream's publish
  acknowledgment. Retries reuse `Nats-Msg-Id`; notification inbox uniqueness
  deduplicates even after the broker's two-minute deduplication window.
- The receiver commits its inbox and pending delivery in one transaction, then
  acknowledges NATS. Lost acknowledgments cause safe redelivery. Invalid events
  are logged without their payload and retried, so operators can investigate
  without silently discarding them.
- Relay and delivery claims last 120 seconds. Transactions release locks before
  network calls; expired claims can be reclaimed. Completion and retry updates
  check the claim token and its unexpired lease. Database time governs leases.
- Failed work backs off from 10 seconds to one hour. HTTP delivery times out after
  15 seconds per network operation; NATS publish/ack waits are 10 seconds.
  A worker crash leaves pending work recoverable after its lease expires.
- Discord delivery is **at least once**. A crash after Discord accepts a message
  but before MySQL records success can cause a duplicate. Exactly-once external
  delivery is not guaranteed.
- The local `OFFERS` stream uses file storage, work-queue retention, and a 1 GiB
  bound with `DiscardNew`. It refuses new work when full, leaving that work in
  source outboxes. It has no automatic age expiry. The single local NATS server
  is not highly available; production resilience needs a managed/replicated
  deployment and tested backups.

Inspect `outbox` in the relevant source database and `deliveries` in the
notification database: `completed_at IS NULL` identifies pending work;
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
payloads or outbox events. Legacy rows cannot prove Discord delivery because the
old writer ordering could record terminal success before Discord failed. Keep
the original database for reconciliation. No legacy importer is run automatically.
Do not use `docker compose down -v` on an existing deployment.

## Deployment and validation

Railway staging is defined in `.railway/railway.ts`. It creates the services,
private connections, persistent volumes, generated passwords, and collector schedules.
Use the [Railway deployment guide](docs/railway.md) for the initial deployment and updates.
Discord delivery starts with zero replicas until you configure a staging webhook.

Docker builds use the repository root as context. Select the service directory name
as the target, for example `docker build --target wttj -t bovie-wttj .`.
Each final image contains only that service and its installed dependencies.
The default Docker target remains Business France.

The old `bovie-worker` and `bovie-migrate DOMAIN` commands are removed.
Replace them with the commands above when updating an existing deployment.
Existing MySQL tables, Alembic revision IDs, and version-1 events remain compatible.
Remove `WTTJ_QUERY=VIE` from an existing environment to enable the broader default.
Collection can create more notifications once non-VIE offers enter the scan window.

```sh
uv run --all-packages ruff check services packages tests scripts
uv run --all-packages ty check
uv run --all-packages pytest
uv build --all-packages --out-dir dist/workspace
uv run --all-packages python scripts/check_packages.py dist/workspace
```

To include integration tests, point these **test-only** variables at disposable
servers. The MySQL fixture creates and drops uniquely named test databases/users;
the NATS test creates and deletes its test stream. Never point them at production.

```sh
MYSQL_TEST_ADMIN_URL='mysql+pymysql://root:test-password@127.0.0.1:33077/mysql' \
NATS_TEST_URL='nats://127.0.0.1:42277' uv run --all-packages pytest
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
