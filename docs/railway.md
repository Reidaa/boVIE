# Deploy to Railway staging

The configuration in `.railway/railway.ts` defines the staging environment in the
`boVIE` Railway project. It deploys from `Reidaa/boVIE`, branch `feat/wttf`.
After this branch merges, change the source branch in that file to `main`.
The configuration refuses to target production. Production still has the legacy
app and Postgres database and requires a separate migration plan.

Install Node.js 22.18 or later and Python 3.13 or later for local development.
The Railway tooling uses its own package file and lockfile inside `.railway/`.
Application images contain Python packages only.

```sh
npm ci --prefix .railway
.railway/node_modules/.bin/railway login
.railway/node_modules/.bin/railway link --project boVIE --environment staging
npm --prefix .railway run check
npm --prefix .railway run plan
npm --prefix .railway run apply
```

`check` runs Oxfmt, Oxlint, TypeScript, and the Railway configuration tests.
Run `npm --prefix .railway run format` to format the TypeScript files.

For a new project, first create the project and an empty staging environment in Railway.
The plan must target `staging`. A new environment gets three Railway MySQL databases,
eight application or broker services, and one NATS volume.
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
| `business-france` | Scheduled collection at minute 12, every two hours UTC | `bovie` |
| `wttj` | Scheduled collection at minute 22, every two hours UTC | `wttf` |
| `broker-setup` | Provision the stream and consumer, then exit | `broker-setup` |
| `relay-bf` | Publish Business France events | `outbox-relay --source business_france` |
| `relay-wttj` | Publish WTTJ events | `outbox-relay --source wttj` |
| `notification-intake` | Store events and pending deliveries | `notification-intake` |
| `discord-delivery` | Send pending deliveries, initially stopped | `discord-delivery` |

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
The database library accepts Railway's `mysql://` URL and uses PyMySQL.
Generated passwords start with `bovie_` so NATS reads them as strings.
Retain an alphabetic prefix when rotating NATS passwords.

The collectors run `source-migrate --wait-timeout 180` before deployment.
Notification intake runs `notification-migrate --wait-timeout 180`.
The Business France collector reads the current public API key from the official offers page before calling its search API.
These commands wait for database connectivity before applying migrations.
Migration failures stop the deployment and are not retried as connection failures.
Workers retry while their database or broker is starting.
Broker setup exits successfully after provisioning and runs again when redeployed.

## Enable staging Discord delivery

Discord delivery starts as an empty service without a source connection.
Railway requires at least one replica, so zero replicas cannot stop a service.
Collection and intake can run while Discord delivery is stopped.
Pending notifications stay in the notification database until delivery starts.
Create a webhook for a staging Discord channel and set `DISCORD_WEBHOOK_URL`
on the `discord-delivery` service in Railway. Keep the value out of this repository.

Change `deliveryEnabled` from `false` to `true` in `.railway/railway.ts`.
The apply connects the service to GitHub and starts its first deployment.
Run the checks, plan, and apply commands again.
Starting delivery sends all pending staging discoveries, including older queued offers.

## Updates and checks

Push changes to the configured branch to trigger Railway builds for affected services.
Run `npm --prefix .railway run plan` after changing infrastructure configuration.
Apply the reviewed plan to update the service configuration.
The old root `railway.json` is removed because it only described Business France.

```sh
.railway/node_modules/.bin/railway status
.railway/node_modules/.bin/railway logs --service business-france --lines 50
.railway/node_modules/.bin/railway logs --service notification-intake --lines 50
npm --prefix .railway run plan
```

Collectors and broker setup finish after successful runs. That exit is expected.
The relay and intake services must stay running. Delivery must remain stopped until its webhook is configured.
A repeated plan after deployment must show no changes.

The configuration follows Railway's [Infrastructure as Code guide](https://docs.railway.com/infrastructure-as-code)
and [pre-deploy command documentation](https://docs.railway.com/deployments/pre-deploy-command).
Railway account access is required for live plan and apply checks.
Local configuration tests and container builds do not need account credentials.
