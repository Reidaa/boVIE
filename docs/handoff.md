# Service ownership

The project collects general job offers from WTTJ and VIE/VIA offers from Business France.
The uv workspace separates six deployable services from six shared libraries.
Each service declares its own dependencies and has a dedicated Docker target.
The root project installs development tools only.

| Library | Owns | Used by |
| --- | --- | --- |
| `job_contracts` | Version-1 discovery events | Collectors, relay, intake, delivery |
| `source_store` | Offers, checkpoints, outbox, source migrations | Collectors and relay |
| `notification_store` | Inbox, pending deliveries, atomic acceptance, notification migrations | Intake and delivery |
| `job_database` | MySQL connections, UTC timestamps, queue leases, migration execution | Both storage libraries and database clients |
| `job_messaging` | NATS connection configuration and stream names | Relay, intake, broker setup |
| `job_runtime` | Entrypoint environment loading and failure logging | Deployable services |

A library cannot import a service. A service cannot import another service.
`tests/test_architecture.py` checks these rules and declared workspace dependencies.
`scripts/check_packages.py` installs each service from wheels into a separate environment.
It checks entrypoints, packaged migrations, and the absence of unrelated service code.

The old shared worker command is removed. Each worker has one role.
Collectors cannot send Discord messages. The Discord delivery package has no NATS client.
Broker setup has no database dependency. The relay uses one source database per deployment.
Intake and delivery share the notification database and never query source databases.

The MySQL tables, Alembic revision IDs, event version, and NATS subjects are unchanged.
Existing databases do not require a data transfer for this package split.
Collection restarts replay from the beginning because search results can move between runs.
One active collector per source remains the supported mode.
Queue claims expire after 120 seconds. Discord delivery remains at least once.
A crash after Discord accepts a message can produce a duplicate on retry.

WTTJ defaults to an empty title query and no contract filter.
The API requires the `job_title` parameter even when its value is empty.
Only published job details enter storage. Optional contract filters apply to search and detail responses.
The scan remains bounded by public search results, `--limit`, and `--max-pages`.
Remove any existing `WTTJ_QUERY=VIE` setting to adopt the broader default.

No legacy Postgres data is transferred or deleted. Retain that database if its offer history is required.
Production deployments still need separate credentials, TLS, backups, and a broker availability plan.
The Compose passwords are local development examples.
Use the [README](../README.md) for commands and the [WTTJ request contract](wttj-api.md) for observed API behavior.

Railway staging uses `.railway/railway.ts` with three native MySQL services and
explicit Dockerfiles for application and broker services.
The configuration refuses to target production. See [Railway deployment](railway.md).
Migration commands accept `--wait-timeout` for initial database startup.
Only connection attempts are retried. A failed schema migration stops deployment.
