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

  const businessFranceDb = mysql("mysql-business-france", { region });
  const wttjDb = mysql("mysql-wttj", { region });
  const notificationsDb = mysql("mysql-notifications", { region });
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
      NATS_ADMIN_PASSWORD: secret("nats", "NATS_ADMIN_PASSWORD"),
      NATS_BF_PASSWORD: secret("nats", "NATS_BF_PASSWORD"),
      NATS_WTTJ_PASSWORD: secret("nats", "NATS_WTTJ_PASSWORD"),
      NATS_NOTIFICATIONS_PASSWORD: secret("nats", "NATS_NOTIFICATIONS_PASSWORD"),
    },
  });
  const broker = (user: string, password: string) => ({
    NATS_URL: "nats://${{nats.RAILWAY_PRIVATE_DOMAIN}}:4222",
    NATS_USER: user,
    NATS_PASSWORD: `\${{nats.${password}}}`,
  });
  const bfDatabase = { DATABASE_URL: businessFranceDb.env.MYSQL_URL };
  const wttjDatabase = { DATABASE_URL: wttjDb.env.MYSQL_URL };
  const notificationDatabase = { DATABASE_URL: notificationsDb.env.MYSQL_URL };
  const businessFrance = app("collector-business-france", "collector-business-france", {
    start: "collector-business-france",
    preDeploy: "source-migrate --wait-timeout 180",
    deploy: { cronSchedule: "12 */2 * * *", restartPolicyType: "NEVER" },
    env: { ...bfDatabase, ...broker("business_france", "NATS_BF_PASSWORD"), BOVIE_LIMIT: "25" },
  });
  const wttj = app("collector-wttj", "collector-wttj", {
    start: "collector-wttj",
    preDeploy: "source-migrate --wait-timeout 180",
    deploy: { cronSchedule: "22 */2 * * *", restartPolicyType: "NEVER" },
    env: {
      ...wttjDatabase,
      ...broker("wttj", "NATS_WTTJ_PASSWORD"),
      WTTJ_QUERY: "",
      WTTJ_CONTRACTS: "",
      WTTJ_LIMIT: "50",
      WTTJ_MAX_PAGES: "5",
    },
  });
  const setup = app("nats-setup", "nats-setup", {
    start: "nats-setup",
    env: broker("admin", "NATS_ADMIN_PASSWORD"),
  });
  const intake = app("discord-intake", "discord-intake", {
    start: "discord-intake",
    preDeploy: "notification-migrate --wait-timeout 180",
    env: { ...notificationDatabase, ...broker("notifications", "NATS_NOTIFICATIONS_PASSWORD") },
  });
  const delivery = app("discord-sender", "discord-sender", {
    start: "discord-sender",
    source: deliveryEnabled ? source : undefined,
    env: {
      ...notificationDatabase,
      DISCORD_WEBHOOK_URL: secret("discord-sender", "DISCORD_WEBHOOK_URL"),
    },
  });
  return project(ctx.projectName ?? "boVIE", {
    resources: [
      businessFranceDb,
      wttjDb,
      notificationsDb,
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
