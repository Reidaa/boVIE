# Deploy to Railway staging

The configuration in `infra/railway/railway.ts` defines the staging environment in the
`boVIE` Railway project. It deploys from `Reidaa/boVIE`, branch `feat/wttf`.
After this branch merges, change the source branch in that file to `main`.
The configuration refuses to target production. Production still has the legacy
app and Postgres database and requires a separate migration plan.

Install Node.js 22.18 or later and Python 3.13 or later for local development.
The Railway tooling is the `bovie-railway` npm workspace in `infra/railway/`.
It shares the root `package-lock.json`. Application images contain Python packages only.

```sh
npm ci
npx railway login
npx railway link --project boVIE --environment staging
npx turbo run lint format:check check test --filter=bovie-railway
npm run railway:plan
npm run railway:apply
```

The Turborepo tasks run Oxlint, Oxfmt, TypeScript, and the Railway configuration tests.
Run `npx turbo run format --filter=bovie-railway` to format the TypeScript files.

For a new project, first create the project and an empty staging environment in Railway.
The plan must target `staging`. A new environment gets three Railway MySQL databases,
six application or broker services, and one NATS volume.
`apply` displays the plan before confirmation.
The deployment uses private networking and creates no public domains or database proxies.
Do not use this configuration to replace an existing production environment.

## Services and storage

| Service | Role | Start command |
| --- | --- | --- |
| `mysql-business-france` | Business France data | Railway MySQL |
| `mysql-wttj` | WTTJ data | Railway MySQL |
| `mysql-notifications` | Inbox and pending deliveries | Railway MySQL |
| `nats` | Persistent JetStream broker | NATS with the repository configuration |
| `collector-business-france` | Collect and publish at minute 12, every two hours UTC | `collector-business-france` |
| `collector-wttj` | Collect and publish at minute 22, every two hours UTC | `collector-wttj` |
| `nats-setup` | Create the stream and consumer, then exit | `nats-setup` |
| `discord-intake` | Read offers and queue Discord messages | `discord-intake` |
| `discord-sender` | Post queued messages to Discord, initially stopped | `discord-sender` |

Every application or broker service uses the repository root as its build context and has an explicit Dockerfile path.
Each application image installs only its workspace package and dependencies.
Railway creates and mounts storage for each MySQL database.
NATS stores JetStream data on `nats-data`, mounted at `/data`.
NATS requires its volume mount before starting.
All services run in `europe-west4-drams3a`.

The plan and apply scripts generate missing NATS passwords with Node.js cryptographic randomness.
They pass new values to the configuration through the local process environment.
Existing values, including sealed variables, are preserved on later applies.
Use these npm scripts for the first deployment so NATS credentials are initialized.
Railway provisions MySQL connection variables. Each worker references only its database's `MYSQL_URL`.
Each collector references only its own source's NATS password.
The database library accepts Railway's `mysql://` URL and uses PyMySQL.
Generated passwords start with `bovie_` so NATS reads them as strings.
Retain an alphabetic prefix when rotating NATS passwords.

The collectors run `source-migrate --wait-timeout 180` before deployment.
`discord-intake` runs `notification-migrate --wait-timeout 180`.
The Business France collector reads the current public API key from the official offers page before calling its search API.
These commands wait for database connectivity before applying migrations.
Migration failures stop the deployment and are not retried as connection failures.
Workers retry while their database or broker is starting.
`nats-setup` exits successfully after provisioning and runs again when redeployed.

## Enable staging Discord delivery

`discord-sender` starts as an empty service without a source connection.
Railway requires at least one replica, so zero replicas cannot stop a service.
Collection and `discord-intake` can run while `discord-sender` is stopped.
Pending notifications stay in the notification database until delivery starts.
Create a webhook for a staging Discord channel and set `DISCORD_WEBHOOK_URL`
on the `discord-sender` service in Railway. Keep the value out of this repository.

Change `deliveryEnabled` from `false` to `true` in `infra/railway/railway.ts`.
The apply connects the service to GitHub and starts its first deployment.
Run the checks, plan, and apply commands again.
Starting delivery sends all pending staging discoveries, including older queued offers.

## Updates and checks

Push changes to the configured branch to trigger Railway builds for affected services.
Run `npm run railway:plan` after changing infrastructure configuration.
Apply the reviewed plan to update the service configuration.

```sh
npx railway status
npx railway logs --service collector-business-france --lines 50
npx railway logs --service discord-intake --lines 50
npm run railway:plan
```

Collectors and broker setup finish after successful runs. That exit is expected.
`discord-intake` must stay running. `discord-sender` must remain stopped until its webhook is configured.
A repeated plan after deployment must show no changes.

The configuration follows Railway's [Infrastructure as Code guide](https://docs.railway.com/infrastructure-as-code)
and [pre-deploy command documentation](https://docs.railway.com/deployments/pre-deploy-command).
Railway account access is required for live plan and apply checks.
Local configuration tests and container builds do not need account credentials.
