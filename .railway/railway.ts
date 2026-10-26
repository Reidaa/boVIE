import {
  defineRailway,
  github,
  mysql,
  preserve,
  project,
  service,
  volume,
  type ServiceConfigInput,
} from "railway/iac";

const region = "europe-west4-drams3a";
const bootstrap: Record<string, Record<string, string>> = JSON.parse(
  process.env.BOVIE_RAILWAY_BOOTSTRAP_SECRETS ?? "{}",
);
const secret = (owner: string, key: string) => bootstrap[owner]?.[key] ?? preserve();
// Railway does not copy sealed values into PR environments.
const sealed = (owner: string, key: string) => {
  const value = bootstrap[owner]?.[key];
  return value === undefined ? preserve() : { value, isSealed: true };
};

export default defineRailway((ctx) => {
  // Railway copies production into a temporary environment for each pull request.
  if (ctx.environment !== "production") {
    throw new Error("This configuration manages only production.");
  }
  // Railway deploys a commit on main only after its GitHub checks pass.
  const source = github("Reidaa/boVIE", { branch: "main", checkSuites: true, rootDirectory: "/" });
  const replicas = { [region]: 1 };
  const app = (name: string, packageName: string, config: ServiceConfigInput) =>
    service(name, {
      source,
      build: {
        builder: "DOCKERFILE",
        dockerfilePath: `apps/${packageName}/Dockerfile`,
        watchPatterns: [
          `apps/${packageName}/**`,
          "packages/**",
          "pyproject.toml",
          "uv.lock",
          ".railway/**",
        ],
      },
      replicas,
      ...config,
      deploy: {
        ...config.deploy,
        restartPolicyMaxRetries: config.deploy?.restartPolicyType === "NEVER" ? undefined : 100,
      },
    });

  const businessFranceDb = mysql("mysql-collector-business-france", { region });
  const wttjDb = mysql("mysql-collector-wttj", { region });
  const discordDb = mysql("mysql-discord", { region });
  const natsJetstream = volume("nats-jetstream", { region, sizeMB: 2048 });
  const nats = service("nats", {
    source,
    build: {
      builder: "DOCKERFILE",
      dockerfilePath: "deploy/railway/nats/Dockerfile",
      watchPatterns: ["deploy/railway/nats/**", "deploy/nats.conf"],
    },
    replicas,
    deploy: { requiredMountPath: "/data", restartPolicyMaxRetries: 100 },
    volumeMounts: { "/data": natsJetstream },
    env: {
      NATS_SETUP_PASSWORD: secret("nats", "NATS_SETUP_PASSWORD"),
      NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD: secret(
        "nats",
        "NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD",
      ),
      NATS_COLLECTOR_WTTJ_PASSWORD: secret("nats", "NATS_COLLECTOR_WTTJ_PASSWORD"),
      NATS_DISCORD_INTAKE_PASSWORD: secret("nats", "NATS_DISCORD_INTAKE_PASSWORD"),
    },
  });
  const broker = (user: string, password: keyof typeof nats.env) => ({
    NATS_URL: "nats://${{nats.RAILWAY_PRIVATE_DOMAIN}}:4222",
    NATS_USER: user,
    NATS_PASSWORD: nats.env[password],
  });
  const businessFranceDatabase = { DATABASE_URL: businessFranceDb.env.MYSQL_URL };
  const wttjDatabase = { DATABASE_URL: wttjDb.env.MYSQL_URL };
  const discordDatabase = { DATABASE_URL: discordDb.env.MYSQL_URL };
  const businessFrance = app("collector-business-france", "collector-business-france", {
    start: "collector-business-france",
    preDeploy: "collector-store-migrate --wait-timeout 180",
    deploy: { cronSchedule: "12 */2 * * *", restartPolicyType: "NEVER" },
    env: {
      ...businessFranceDatabase,
      ...broker("collector-business-france", "NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD"),
      BUSINESS_FRANCE_LIMIT: "25",
      BUSINESS_FRANCE_REGION: "asie et pacifique,amerique latine,amerique du nord",
      // Optional; set in Railway when needed.
      BUSINESS_FRANCE_API_KEY: preserve(),
    },
  });
  const wttj = app("collector-wttj", "collector-wttj", {
    start: "collector-wttj",
    preDeploy: "collector-store-migrate --wait-timeout 180",
    deploy: { cronSchedule: "22 */2 * * *", restartPolicyType: "NEVER" },
    env: {
      ...wttjDatabase,
      ...broker("collector-wttj", "NATS_COLLECTOR_WTTJ_PASSWORD"),
      WTTJ_QUERY: "",
      WTTJ_CONTRACTS: "",
      WTTJ_LIMIT: "50",
      WTTJ_MAX_PAGES: "5",
    },
  });
  const setup = app("nats-setup", "nats-setup", {
    start: "nats-setup",
    env: broker("nats-setup", "NATS_SETUP_PASSWORD"),
  });
  const intake = app("discord-intake", "discord-intake", {
    start: "discord-intake",
    preDeploy: "discord-store-migrate --wait-timeout 180",
    env: { ...discordDatabase, ...broker("discord-intake", "NATS_DISCORD_INTAKE_PASSWORD") },
  });
  const delivery = app("discord-sender", "discord-sender", {
    start: "discord-sender",
    env: {
      ...discordDatabase,
      // PR environments run without it, so only production posts to Discord.
      DISCORD_WEBHOOK_URL: sealed("discord-sender", "DISCORD_WEBHOOK_URL"),
    },
  });
  return project(ctx.projectName ?? "boVIE", {
    resources: [
      businessFranceDb,
      wttjDb,
      discordDb,
      natsJetstream,
      nats,
      businessFrance,
      wttj,
      setup,
      intake,
      delivery,
    ],
  });
});
