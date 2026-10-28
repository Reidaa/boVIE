# Deploy to Railway

The `production` environment of the `boVIE` Railway project deploys `Reidaa/boVIE`, branch `main`.
Its configuration lives in the Railway dashboard. This repository holds no Railway configuration.
Railway deploys a commit only after every GitHub workflow for that commit passes.

Railway creates a temporary PR environment for each pull request and deletes it when the
pull request closes. A PR environment copies production and deploys the pull request branch.
It gets fresh databases and its own broker. It does not post to Discord: Railway does not copy
the sealed `DISCORD_WEBHOOK_URL`, so `discord-sender` logs a warning and exits.

The deployment uses private networking and creates no public domains or database proxies.

## Services and storage

| Service | Role | Start command |
| --- | --- | --- |
| `mysql-collector-business-france` | Business France data | Railway MySQL |
| `mysql-collector-wttj` | WTTJ data | Railway MySQL |
| `mysql-discord` | Inbox and pending deliveries | Railway MySQL |
| `nats` | Persistent JetStream broker | NATS with the repository configuration |
| `collector-business-france` | Collect and publish at minute 12, every two hours UTC | `collector-business-france` |
| `collector-wttj` | Collect and publish at minute 22, every two hours UTC | `collector-wttj` |
| `nats-setup` | Create the stream and consumer, then exit | `nats-setup` |
| `discord-intake` | Read offers and queue Discord messages | `discord-intake` |
| `discord-sender` | Post queued messages to Discord | `discord-sender` |

Every application or broker service uses the repository root as its build context and has an explicit Dockerfile path.
Each application image installs only its workspace package and dependencies.
Railway creates and mounts storage for each MySQL database.
NATS stores JetStream data on `nats-jetstream`, mounted at `/data`.
NATS requires its volume mount before starting.
All services run in `europe-west4-drams3a`.

`DISCORD_WEBHOOK_URL` is a sealed variable. Keep the value out of this repository.
Railway provisions MySQL connection variables. Each worker references only its database's `MYSQL_URL`.
Each app references only its own NATS password.
The database library accepts Railway's `mysql://` URL and uses PyMySQL.
NATS passwords start with `bovie_` so NATS reads them as strings.
Retain an alphabetic prefix when rotating NATS passwords.

The collectors run `collector-store-migrate --wait-timeout 180` before deployment.
`discord-intake` runs `discord-store-migrate --wait-timeout 180`.
The Business France collector uses `BUSINESS_FRANCE_API_KEY` when it is set in Railway.
Otherwise it reads the public API key from the official offers page.
After a 401 response, it reads the page again and retries once.
These commands wait for database connectivity before applying migrations.
Migration failures stop the deployment and are not retried as connection failures.
Workers retry while their database or broker is starting.
`nats-setup` exits successfully after provisioning and runs again when redeployed.

## Updates and checks

Merge to `main` to trigger Railway builds for affected services.
A failed workflow on `main` blocks that commit's deployment.
Change services, variables, and schedules in the Railway dashboard.

With the [Railway CLI](https://docs.railway.com/guides/cli) installed and linked to `boVIE`:

```sh
railway status
railway logs --service collector-business-france --lines 50
railway logs --service discord-intake --lines 50
```

Collectors and broker setup finish after successful runs. That exit is expected.
`discord-intake` and `discord-sender` must stay running in production.
