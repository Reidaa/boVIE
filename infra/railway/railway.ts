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

export const deliveryEnabled: boolean = false;

const region = "europe-west4-drams3a";
const bootstrap: Record<string, Record<string, string>> = JSON.parse(
  process.env.BOVIE_RAILWAY_BOOTSTRAP_SECRETS ?? "{}",
);
const secret = (owner: string, key: string) => bootstrap[owner]?.[key] ?? preserve();

export default defineRailway((ctx) => {
  if (ctx.environment !== "staging") {
    throw new Error(
      "This deployment targets staging. Review the existing production resources before promoting it.",
    );
  }
  const source = github("Reidaa/boVIE", { branch: "feat/wttf", rootDirectory: "/" });
  const persistent = {
    multiRegionConfig: { [region]: { numReplicas: 1 } },
    restartPolicyMaxRetries: 100,
  };
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
          "infra/railway/**",
        ],
      },
      ...config,
      deploy: {
        ...persistent,
        ...config.deploy,
        restartPolicyMaxRetries: config.deploy?.restartPolicyType === "NEVER" ? undefined : 100,
      },
    });

  const businessFranceDb = mysql("mysql-collector-business-france", { region });
  const wttjDb = mysql("mysql-collector-wttj", { region });
  const discordDb = mysql("mysql-discord", { region });
  const natsData = volume("nats-data", { region, sizeMB: 2048 });
  const nats = service("nats", {
    source,
    build: {
      builder: "DOCKERFILE",
      dockerfilePath: "deploy/railway/nats/Dockerfile",
      watchPatterns: ["deploy/railway/nats/**", "deploy/nats.conf"],
    },
    deploy: { ...persistent, requiredMountPath: "/data" },
    volumeMounts: { "/data": natsData },
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
  const broker = (user: string, password: string) => ({
    NATS_URL: "nats://${{nats.RAILWAY_PRIVATE_DOMAIN}}:4222",
    NATS_USER: user,
    NATS_PASSWORD: `\${{nats.${password}}}`,
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
    source: deliveryEnabled ? source : undefined,
    env: {
      ...discordDatabase,
      DISCORD_WEBHOOK_URL: secret("discord-sender", "DISCORD_WEBHOOK_URL"),
    },
  });
  return project(ctx.projectName ?? "boVIE", {
    resources: [
      businessFranceDb,
      wttjDb,
      discordDb,
      natsData,
      nats,
      businessFrance,
      wttj,
      setup,
      intake,
      delivery,
    ],
  });
});
