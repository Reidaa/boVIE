# Service ownership

The project collects general job offers from WTTJ and VIE/VIA offers from Business France.
The uv workspace separates five deployable services from six shared libraries.
Each service declares its own dependencies and has a dedicated Docker target.
The root project installs development tools only.

| Library | Owns | Used by |
| --- | --- | --- |
| `offer_events` | Version-1 offer events with stable event IDs | Collectors, `discord-intake`, `discord-sender` |
| `collector_store` | Published offers, content hashes, sightings, checkpoints, collector database migrations | Collectors |
| `discord_store` | Inbox, queued messages, atomic acceptance, Discord database migrations | `discord-intake` and `discord-sender` |
| `mysql_common` | MySQL connections, UTC timestamps, queue leases, migration execution | Both storage libraries and database clients |
| `nats_client` | NATS connection, stream names, and the collectors' synchronous publisher | Collectors, `discord-intake`, `nats-setup` |
| `cli_common` | Entrypoint environment loading and failure logging | Deployable services |

A library cannot import a service. A service cannot import another service.
`tests/test_architecture.py` checks these rules and declared workspace dependencies.
`scripts/check_packages.py` installs each service from wheels into a separate environment.
It checks entrypoints, packaged migrations, and the absence of unrelated service code.

Each worker has one role.
Collectors cannot send Discord messages. `discord-sender` has no NATS client.
`nats-setup` has no database dependency. Each collector publishes only its own source's subject.
`discord-intake` and `discord-sender` share the `discord` database and never query collector databases.

Collectors publish each page and wait for JetStream acknowledgments before recording it.
A crash in between republishes the same event IDs; the Discord inbox drops the duplicates.
Collection restarts replay from the beginning because search results can move between runs.
One active collector per source is the supported mode.
The stream keeps acknowledged messages for 90 days, so new consumers can replay them.
Delivery claims expire after 120 seconds. Discord delivery is at least once.
A crash after Discord accepts a message can produce a duplicate on retry.

WTTJ defaults to an empty title query and no contract filter.
The API requires the `job_title` parameter even when its value is empty.
Only published job details enter storage. Optional contract filters apply to search and detail responses.
The scan remains bounded by public search results, `--limit`, and `--max-pages`.

Production deployments still need separate credentials, TLS, backups, and a broker availability plan.
The Compose passwords are local development examples.
Use the [README](../README.md) for commands and the [WTTJ request contract](wttj-api.md) for observed API behavior.

Railway staging uses `infra/railway/railway.ts` with three native MySQL services and
explicit Dockerfiles for application and broker services.
The configuration refuses to target production. See [Railway deployment](railway.md).
Migration commands accept `--wait-timeout` for initial database startup.
Only connection attempts are retried. A failed schema migration stops deployment.
