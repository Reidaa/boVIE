# SQLAlchemy / MySQL / NATS handover

Implemented on `feat/wttf`, based on `8d87458`. The initial working tree was clean.
The original baseline passed 16 tests, Ruff, and ty.

The implementation follows the synchronous SQLAlchemy 2 / PyMySQL / Alembic
approach from the handoff. Shared tables would compromise source independence;
a broker adds operational work. The user explicitly selected NATS during
implementation, so JetStream replaces the proposed HTTP ingestion transport.
MySQL databases and credentials are separate per source and for notifications.

Key seams:

- `bovie.events`: validated version-1 discovery contract with complete rendering data.
- `bovie.collector`: source-owned offers, checkpoints, and transactional outbox.
- `bovie.notifications`: independently owned inbox and pending Discord deliveries.
- `bovie.queue`: short MySQL claims, expiry, retry, and ownership-checked completion.
- `bovie.transport`: JetStream provisioning, source relay, receiver, and delivery CLI.
- `bovie.migrations`: separate packaged Alembic histories for source and notification schemas.
- `wttf.core.search`: verified current WTTJ v3 projections; legacy models remain intact.

Collection restarts replay from the beginning instead of trusting stale offsets.
This avoids skipping an interrupted page due to a prematurely advanced local
checkpoint, but no offset/ranked API guarantees an exhaustive snapshot. One active
collector per source is the supported mode. Relays and delivery workers use leases
and can share their own domain database. External Discord delivery remains at least
once. Inbox/outbox history is retained indefinitely until an explicit retention
policy is designed.

Validation uses real disposable MySQL and NATS plus mocked source/Discord HTTP.
Final result: 41 tests passed on CPython 3.14.7, including the exact deployment
NATS permission configuration. Ruff, ty, pre-commit (including workflow
validation), and Compose configuration checks passed. Disposable test containers
and their test-only data were removed after validation.
The wheel is built from the source distribution and checked in an isolated
environment for both entrypoints and packaged migrations. CI runs the real-service
suite. All changed Actions references use full commits with resolved exact release
comments.

Before production deployment:

- Decide whether legacy Postgres seen IDs need an explicit idempotent export/import.
  No live data was migrated; an importer is not included. Retain the original DB.
- Provision production secrets, database grants, TLS, and NATS availability/backups.
  The Compose passwords and one-node JetStream setup are local development defaults.
- Configure and schedule one collector per source and independent relay/receiver/
  delivery services. Railway's checked-in cron configuration covers Business France.
- Set WTTJ search terms and scan depth with awareness that public ranked search is
  not a complete discovery feed. The verified contract is in `wttj-api.md`.
