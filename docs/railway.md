# Deploy to Railway

The `production` environment of the `boVIE` Railway project deploys `Reidaa/boVIE`, branch `main`.
[Railway Infrastructure as Code](https://docs.railway.com/infrastructure-as-code) in
[`.railway/railway.ts`](../.railway/railway.ts) defines its services, databases, volumes, schedules,
and variables. Railway deploys a commit only after every GitHub workflow for that commit passes.

Railway creates a temporary PR environment for each pull request and deletes it when the
pull request closes. A PR environment copies production and deploys the pull request branch.
It gets an empty MySQL server and its own broker. It does not post to Discord: Railway does not copy
the sealed `DISCORD_WEBHOOK_URL`, so `discord-sender` logs a warning and exits.

The deployment uses private networking and creates no public domains or database proxies.

## Services and storage

| Service | Role | Start command |
| --- | --- | --- |
| `mysql` | One MySQL server with the databases of all apps | Railway MySQL |
| `nats` | Persistent JetStream broker | NATS with the repository configuration |
| `collector-business-france` | Collect and publish at minute 12, every two hours UTC | `collector-business-france` |
| `collector-wttj` | Collect and publish at minute 22, every two hours UTC | `collector-wttj` |
| `collector-workday` | Collect and publish at minute 32, every two hours UTC | `collector-workday` |
| `discord-intake` | Read offers and queue Discord messages | `discord-intake` |
| `discord-sender` | Post queued messages to Discord | `discord-sender` |

Every application or broker service uses the repository root as its build context and has an explicit Dockerfile path.
Each application image installs only its workspace package and dependencies.
Railway creates and mounts the storage of `mysql`.
`mysql` holds one database per app: `collector_business_france`, `collector_wttj`,
`collector_workday`, and `discord`. `discord-intake` and `discord-sender` share `discord`.
NATS stores JetStream data on `nats-jetstream`, mounted at `/data`.
NATS requires its volume mount before starting.
All services run in `europe-west4-drams3a`.

`DISCORD_WEBHOOK_URL` is a sealed variable. Keep the value out of this repository.
Railway provisions the connection variables of `mysql`. Each app builds its `DATABASE_URL`
from them: user `root`, `MYSQL_ROOT_PASSWORD`, the private domain of `mysql`, and its own database.
All apps share the `root` credentials. [ADR 0001](adr/0001-service-based-services-with-one-offer-stream.md) explains why.
Each app references only its own NATS password.
The database library accepts Railway's `mysql://` URL and uses PyMySQL.
NATS passwords start with `bovie_` so NATS reads them as strings.
Retain an alphabetic prefix when rotating NATS passwords.
Use only letters and digits when rotating `MYSQL_ROOT_PASSWORD`: each `DATABASE_URL` contains it without encoding.

The collectors run `collector-store-migrate --wait-timeout 180` before deployment.
`discord-intake` runs `discord-store-migrate --wait-timeout 180`.
`collector-workday` requires `WORKDAY_BOARDS`, the JSON list of boards it collects.
Set it on that service; the repository holds no board list.
The Business France collector uses `BUSINESS_FRANCE_API_KEY` when it is set in Railway.
Otherwise it reads the public API key from the official offers page.
After a 401 response, it reads the page again and retries once.
These commands wait for the MySQL server, create the app's database when it is missing,
then apply migrations.
Migration failures stop the deployment and are not retried as connection failures.
Workers retry while their database or broker is starting.
`discord-sender` has no migration. Until the `discord-intake` migration creates `discord`,
the sender logs each failed attempt and tries again.
On a new broker, the first collector run creates the `OFFERS` stream.
`discord-intake` waits for the stream, then creates its consumer.

## Change the infrastructure

Railway does not apply `.railway/railway.ts` on merge. Apply it yourself.

1. Install the tools with `mise install` and `pnpm install`. Use Railway CLI 5.42.1 or newer.
2. Link this checkout once: `railway link --project boVIE --environment production`.
3. Edit `.railway/railway.ts`.
4. Run `railway config plan` and read the plan.
5. If the plan deletes a database server, copy its data first. See "Move data off a database server".
6. Run `railway config apply` and approve the plan.

The file owns every variable of its services: `apply` removes a variable that the file
does not declare. Secrets and other values kept out of the repository use `preserve()`,
which keeps the value set in Railway. Set these values with the Railway CLI or dashboard:
the NATS passwords, `DISCORD_WEBHOOK_URL` (sealed), and `WORKDAY_BOARDS`.
After `collector-workday` is first created, set `WORKDAY_BOARDS` on it before its first run.

Removing a resource or a variable is destructive. A non-interactive `apply` then also needs
`--confirm-destructive`. Two detached volumes, `postgres-jnxp-volume` and
`mysql-discord-volume-uvDU`, are not in the file; Railway keeps them.

### Move data off a database server

`apply` deletes the volume of a database server with the server, and the data is lost. Copy each
database before you apply. The copy runs inside the private network: the MySQL image has
`mysqldump` and `mysql`, and `railway ssh` forwards standard input. Stop the apps that write to
the old server first, then run these commands for each database. `<database>` is the name of
the app's database on `mysql`.

```sh
railway ssh --service <old server> -- 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --set-gtid-purged=OFF "$MYSQL_DATABASE"' > <database>.sql
railway ssh --service mysql -- 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS <database>"'
railway ssh --service mysql -- 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <database>' < <database>.sql
```

Compare `SELECT COUNT(*)` of each table on both servers. Then point the apps at `mysql` and apply.

The pending apply deletes `mysql-collector-business-france`, `mysql-collector-wttj`,
and `mysql-discord`. Their data was copied to `mysql` on 2026-11-13, and every app has used
`mysql` since then. The old servers hold stale copies, so this deletion loses no data.

PR environments are a project setting in the dashboard. Railway IaC cannot set them.

## Updates and checks

Merge to `main` to trigger Railway builds for affected services.
A failed workflow on `main` blocks that commit's deployment.

With the [Railway CLI](https://docs.railway.com/guides/cli) installed and linked to `boVIE`:

```sh
railway status
railway logs --service collector-business-france --lines 50
railway logs --service discord-intake --lines 50
```

Collectors finish after successful runs. That exit is expected.
`discord-intake` and `discord-sender` must stay running in production.
