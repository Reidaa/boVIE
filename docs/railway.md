# Deploy to Railway

`.railway/railway.ts` defines the `staging` and `production` environments of the
`boVIE` Railway project. It refuses any other environment.
Both environments deploy `Reidaa/boVIE`, branch `main`.
Railway deploys a commit only after every GitHub workflow for that commit passes.
Staging mirrors production. Only production posts to Discord.

Install Node.js 22.18 or later and Python 3.15 or later for local development.
The Railway tooling is the `bovie-railway` npm workspace in `.railway/`.
It shares the root `package-lock.json`. Application images contain Python packages only.

```sh
npm ci
npx railway login
npx railway link --project boVIE
npx turbo run lint format:check check test --filter=bovie-railway
npm run railway:plan -- staging
npm run railway:apply
```

The Turborepo tasks run Oxlint, Oxfmt, TypeScript, and the Railway configuration tests.
Run `npx turbo run format --filter=bovie-railway` to format the TypeScript files.

`railway:plan` links the directory to the named environment and saves the change set
to `railway-plan.json` at the repository root.
`railway:apply` applies exactly that file after confirmation and then deletes it.
The apply fails if the environment or `.railway/` changed after the plan; plan again.
The file can hold generated passwords and is ignored by Git.
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
| `discord-sender` | Post queued messages to Discord; production only | `discord-sender` |

Every application or broker service uses the repository root as its build context and has an explicit Dockerfile path.
Each application image installs only its workspace package and dependencies.
Railway creates and mounts storage for each MySQL database.
NATS stores JetStream data on `nats-jetstream`, mounted at `/data`.
NATS requires its volume mount before starting.
All services run in `europe-west4-drams3a`.

In staging, `discord-sender` has no source connection, so it never runs.
Railway requires at least one replica, so zero replicas cannot stop a service.
Staging discoveries stay queued in its `discord` database.

The plan script generates missing NATS passwords with Node.js cryptographic randomness.
It passes new values to the configuration through the local process environment.
Existing values, including sealed variables, are preserved on later applies.
Create a new environment with the npm scripts so NATS credentials are initialized.
For a new production environment, set `DISCORD_WEBHOOK_URL` in the shell that runs
`railway:plan`. Keep the value out of this repository.
Railway provisions MySQL connection variables. Each worker references only its database's `MYSQL_URL`.
Each app references only its own NATS password.
The database library accepts Railway's `mysql://` URL and uses PyMySQL.
Generated passwords start with `bovie_` so NATS reads them as strings.
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
Railway does not read `.railway/` during deploys. Only a plan and apply change the configuration.

Change the configuration through a pull request to `main`:

1. The `Railway plan` workflow plans both environments and comments each diff on the pull request.
2. A reviewer reads the diffs. Merging is the approval.
3. The `Railway apply` workflow applies those saved plans.

The apply fails if an environment or `.railway/` changed after the plan. Push a new commit to plan again.
The workflow refuses deletions. To delete a resource, run `npm run railway:plan -- <environment>`
and `npm run railway:apply` locally. Then rerun the `Railway plan` workflow, check that it shows
no changes, and merge.
A failed workflow on `main` also blocks that commit's deployment.
The workflows read the `RAILWAY_TOKEN_STAGING` and `RAILWAY_TOKEN_PRODUCTION` repository secrets.
Each is a Railway project token scoped to one environment.

```sh
npx railway status
npx railway logs --service collector-business-france --lines 50
npx railway logs --service discord-intake --lines 50
npm run railway:plan -- production
```

Collectors and broker setup finish after successful runs. That exit is expected.
`discord-intake` and the production `discord-sender` must stay running.
A repeated plan after deployment must show no changes.

The configuration follows Railway's [Infrastructure as Code guide](https://docs.railway.com/infrastructure-as-code)
and [pre-deploy command documentation](https://docs.railway.com/deployments/pre-deploy-command).
Railway account access is required for live plan and apply checks.
Local configuration tests and container builds do not need account credentials.
