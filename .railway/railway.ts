/**
 * Railway infrastructure for the `boVIE` project, as Railway Infrastructure as Code.
 *
 * `railway config plan` compares this file with the linked environment; `railway config apply`
 * changes Railway to match. Railway builds and deploys application code from GitHub on each
 * push to `main`. Secrets never appear here: `preserve()` keeps the value set in Railway.
 * See docs/railway.md.
 */
import { defineRailway, github, mysql, preserve, project, service, volume } from "railway/iac";

const REGION = "europe-west4-drams3a";

/** Railway's MySQL start command with a 1 GiB InnoDB buffer pool. */
const MYSQL_START =
  "docker-entrypoint.sh mysqld --innodb-use-native-aio=0 --disable-log-bin --performance_schema=0 --innodb-buffer-pool-size=1G";

/** Every built service deploys `main` after all GitHub checks of the commit pass. */
const repo = github("Reidaa/boVIE", { branch: "main", checkSuites: true, rootDirectory: "/" });

/**
 * The one MySQL server of the project. Railway creates and mounts its volume. Each app has its
 * own database on it, and its migration command creates that database when it is missing.
 */
function mysqlServer() {
  const server = mysql("mysql", { region: REGION });
  server.deploy = { ...server.deploy, startCommand: MYSQL_START };
  return server;
}

/**
 * The URL of database `name` on the `mysql` server, over the private network. All apps log in as
 * `root`: the data is public offers and pending Discord messages, so shared credentials are
 * accepted. See ADR 0001.
 */
function databaseUrl(name: string) {
  return (
    "mysql://root:${{mysql.MYSQL_ROOT_PASSWORD}}@${{mysql.RAILWAY_PRIVATE_DOMAIN}}:${{mysql.MYSQLPORT}}/" + name
  );
}

/** A Dockerfile build from the repository root that rebuilds only when its inputs change. */
function dockerBuild(dockerfilePath: string, watchPatterns: string[]) {
  return { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath, watchPatterns } as const;
}

/** An app in `apps/<name>`. Its start command is its own name. */
function appService(name: string, config: Omit<Parameters<typeof service>[1], "source" | "build" | "start" | "replicas">) {
  return service(name, {
    source: repo,
    build: dockerBuild(`apps/${name}/Dockerfile`, [`apps/${name}/**`, "packages/**", "pyproject.toml", "uv.lock"]),
    start: name,
    replicas: { [REGION]: 1 },
    ...config,
  });
}

export default defineRailway(() => {
  const jetStream = volume("nats-jetstream", { region: REGION, sizeMB: 2048 });
  const nats = service("nats", {
    source: repo,
    build: dockerBuild("deploy/railway/nats/Dockerfile", ["deploy/railway/nats/**", "deploy/nats.conf"]),
    replicas: { [REGION]: 1 },
    deploy: { requiredMountPath: "/data", restartPolicyMaxRetries: 100 },
    volumeMounts: { "/data": jetStream },
    env: {
      NATS_SETUP_PASSWORD: preserve(),
      NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD: preserve(),
      NATS_COLLECTOR_WTTJ_PASSWORD: preserve(),
      NATS_COLLECTOR_WORKDAY_PASSWORD: preserve(),
      NATS_DISCORD_INTAKE_PASSWORD: preserve(),
    },
  });

  /** Connection variables for an app that logs in to NATS as `user`. */
  const natsEnv = (user: string, password: keyof typeof nats.env) => ({
    NATS_URL: "nats://${{nats.RAILWAY_PRIVATE_DOMAIN}}:4222",
    NATS_USER: user,
    NATS_PASSWORD: nats.env[password],
  });

  /** A collector that runs on `cronSchedule` and migrates its own database before each deploy. */
  const collector = (
    name: string,
    databaseName: string,
    natsPassword: keyof typeof nats.env,
    cronSchedule: string,
    env: Record<string, ReturnType<typeof preserve> | string>,
  ) =>
    appService(name, {
      preDeploy: "collector-store-migrate --wait-timeout 180",
      deploy: { cronSchedule, restartPolicyType: "NEVER" },
      env: { DATABASE_URL: databaseUrl(databaseName), ...natsEnv(name, natsPassword), ...env },
    });

  const server = mysqlServer();

  const businessFrance = collector(
    "collector-business-france",
    "collector_business_france",
    "NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD",
    "12 */2 * * *",
    {
      BUSINESS_FRANCE_REGION: "asie et pacifique,amerique latine,amerique du nord",
      BUSINESS_FRANCE_LIMIT: "25",
    },
  );
  const wttj = collector("collector-wttj", "collector_wttj", "NATS_COLLECTOR_WTTJ_PASSWORD", "22 */2 * * *", {
    WTTJ_QUERY: "",
    WTTJ_CONTRACTS: "",
    WTTJ_LIMIT: "50",
    WTTJ_MAX_PAGES: "5",
  });
  // The board list stays out of the repository. Set WORKDAY_BOARDS in Railway.
  const workday = collector("collector-workday", "collector_workday", "NATS_COLLECTOR_WORKDAY_PASSWORD", "32 */2 * * *", {
    WORKDAY_BOARDS: preserve(),
  });

  const discordIntake = appService("discord-intake", {
    preDeploy: "discord-store-migrate --wait-timeout 180",
    deploy: { restartPolicyMaxRetries: 100 },
    env: { DATABASE_URL: databaseUrl("discord"), ...natsEnv("discord-intake", "NATS_DISCORD_INTAKE_PASSWORD") },
  });
  // DISCORD_WEBHOOK_URL is sealed, so PR environments do not receive it. The sender has no
  // migration: discord-intake's migration creates the shared `discord` database.
  const discordSender = appService("discord-sender", {
    deploy: { restartPolicyMaxRetries: 100 },
    env: { DATABASE_URL: databaseUrl("discord"), DISCORD_WEBHOOK_URL: preserve() },
  });

  return project("boVIE", {
    // This file owns every variable of its services. The CLI reads this policy; the SDK
    // types (railway 3.16.0) do not declare it yet.
    // @ts-expect-error
    variables: { managed: true },
    resources: [
      server,
      jetStream,
      nats,
      businessFrance,
      wttj,
      workday,
      discordIntake,
      discordSender,
    ],
  });
});
