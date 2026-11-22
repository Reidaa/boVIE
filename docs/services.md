# Service ownership

The project collects general job offers from WTTJ and Workday career sites, and VIE/VIA offers
from Business France. The Go module separates five deployable services in `apps/` from six
shared libraries in `packages/`. Each service builds into its own static binary and has its own Dockerfile.

| Library | Owns | Used by |
| --- | --- | --- |
| `offerevents` | Version-1 offer events with stable event IDs | Collectors, `discord-intake`, `discord-sender` |
| `collectorstore` | Published offers, content hashes, sightings, checkpoints, collector database migrations | Collectors |
| `discordstore` | Inbox, queued messages, atomic acceptance, Discord database migrations | `discord-intake` and `discord-sender` |
| `mysqlcommon` | MySQL connections, UTC timestamps, queue leases, SQL migration execution | Both storage libraries and database clients |
| `natsclient` | NATS connection, stream names and settings, stream creation, and the collectors' publisher | Collectors, `discord-intake` |
| `clicommon` | Entrypoint environment loading and redacted failure logging | Deployable services |

A library cannot import a service. A service cannot import another service.
`tests/architecture_test.go` verifies these rules against the Go dependency graph (`go list`),
checks forbidden transitive dependencies per service, and builds and smoke-tests every binary.

Each worker has one role.
Collectors cannot send Discord messages. `discord-sender` has no NATS client.
Each collector publishes only its own source's subject.
Collectors create the `OFFERS` stream when it is missing. `discord-intake` creates its own consumer.
`discord-intake` can update its own consumer, because NATS uses the same request to create and to update a consumer.
No service can update the stream or delete the stream or a consumer. Only the `nats-setup` administrator account can.
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

One Workday collector scans every board in the required `WORKDAY_BOARDS` variable.
Railway sets it on the `collector-workday` service; the repository holds no board list. Each board has its own scan
checkpoint and silent-source check. A failed board fails the run after the other
boards finish. `source_offer_id` is `<tenant>/<site>/<jobPostingId>`.

The Compose passwords are local development examples. Railway generates its own credentials.
Use the [README](../README.md) for commands and the [WTTJ](wttj-api.md) and [Workday](workday-api.md)
request contracts for observed API behavior.

Railway production uses a shared MySQL server with one database per app and
explicit Dockerfiles for application and broker services. Pull requests get temporary copies.
See [Railway deployment](railway.md).
Migration commands accept `--wait-timeout` for initial database startup.
Only connection attempts are retried. A failed schema migration stops deployment.
