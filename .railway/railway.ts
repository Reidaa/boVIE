import {
  defineRailway, github, project, service, volume,
  type ServiceConfigInput, type VariableConfig,
} from "railway/iac";

const region = "europe-west4-drams3a";
const secret = (): VariableConfig => ({ generator: "secret", preserveExisting: true });
const databaseUrl = (owner: string, password: string) =>
  `mysql+pymysql://${owner}:\${{mysql.${password}}}@\${{mysql.RAILWAY_PRIVATE_DOMAIN}}:3306/${owner}`;

export default defineRailway((ctx) => {
  if (ctx.environment !== "staging") {
    throw new Error("This deployment targets staging. Review the existing production resources before promoting it.");
  }
  const source = github("Reidaa/boVIE", { branch: "feat/wttf", rootDirectory: "/" });
  const persistent = {
    region, numReplicas: 1, restartPolicyType: "ON_FAILURE" as const,
    restartPolicyMaxRetries: 100, sleepApplication: false,
  };
  const app = (name: string, packageName: string, config: ServiceConfigInput) => service(name, {
    source,
    build: {
      builder: "DOCKERFILE",
      dockerfilePath: `services/${packageName}/Dockerfile`,
      watchPatterns: [`services/${packageName}/**`, "packages/**", "pyproject.toml", "uv.lock", ".railway/**"],
    },
    ...config,
    deploy: { ...persistent, ...config.deploy },
  });

  const mysqlData = volume("mysql-data", { region, sizeMB: 1024 });
  const natsData = volume("nats-data", { region, sizeMB: 2048 });
  const mysql = service("mysql", {
    source,
    build: { builder: "DOCKERFILE", dockerfilePath: "deploy/railway/mysql/Dockerfile", watchPatterns: ["deploy/railway/mysql/**"] },
    deploy: { ...persistent, requiredMountPath: "/var/lib/mysql" },
    volumeMounts: { "/var/lib/mysql": mysqlData },
    env: {
      MYSQL_ROOT_PASSWORD: secret(),
      BF_DATABASE_PASSWORD: secret(),
      WTTJ_DATABASE_PASSWORD: secret(),
      NOTIFICATION_DATABASE_PASSWORD: secret(),
    },
  });
  const nats = service("nats", {
    source,
    build: { builder: "DOCKERFILE", dockerfilePath: "deploy/railway/nats/Dockerfile", watchPatterns: ["deploy/railway/nats/**", "deploy/nats.conf"] },
    deploy: { ...persistent, requiredMountPath: "/data" },
    volumeMounts: { "/data": natsData },
    env: {
      NATS_ADMIN_PASSWORD: secret(), NATS_BF_PASSWORD: secret(),
      NATS_WTTJ_PASSWORD: secret(), NATS_NOTIFICATIONS_PASSWORD: secret(),
    },
  });
  const broker = (user: string, password: string) => ({
    NATS_URL: "nats://${{nats.RAILWAY_PRIVATE_DOMAIN}}:4222",
    NATS_USER: user,
    NATS_PASSWORD: `\${{nats.${password}}}`,
  });
  const bfDatabase = { DATABASE_URL: databaseUrl("business_france", "BF_DATABASE_PASSWORD") };
  const wttjDatabase = { DATABASE_URL: databaseUrl("wttj", "WTTJ_DATABASE_PASSWORD") };
  const notificationDatabase = { DATABASE_URL: databaseUrl("notifications", "NOTIFICATION_DATABASE_PASSWORD") };
  const businessFrance = app("business-france", "business-france", {
    start: "bovie", preDeploy: "source-migrate --wait-timeout 180",
    deploy: { cronSchedule: "12 */2 * * *", restartPolicyType: "NEVER" },
    env: { ...bfDatabase, BOVIE_LIMIT: "25" },
  });
  const wttj = app("wttj", "wttj", {
    start: "wttf", preDeploy: "source-migrate --wait-timeout 180",
    deploy: { cronSchedule: "22 */2 * * *", restartPolicyType: "NEVER" },
    env: { ...wttjDatabase, WTTJ_QUERY: "", WTTJ_CONTRACTS: "", WTTJ_LIMIT: "50", WTTJ_MAX_PAGES: "5" },
  });
  const setup = app("broker-setup", "broker-setup", {
    start: "broker-setup", env: broker("admin", "NATS_ADMIN_PASSWORD"),
  });
  const relayBf = app("relay-bf", "outbox-relay", {
    start: "outbox-relay --source business_france",
    env: { ...bfDatabase, ...broker("business_france", "NATS_BF_PASSWORD") },
  });
  const relayWttj = app("relay-wttj", "outbox-relay", {
    start: "outbox-relay --source wttj",
    env: { ...wttjDatabase, ...broker("wttj", "NATS_WTTJ_PASSWORD") },
  });
  const intake = app("notification-intake", "notification-intake", {
    start: "notification-intake", preDeploy: "notification-migrate --wait-timeout 180",
    env: { ...notificationDatabase, ...broker("notifications", "NATS_NOTIFICATIONS_PASSWORD") },
  });
  const delivery = app("discord-delivery", "discord-delivery", {
    start: "discord-delivery",
    deploy: { numReplicas: 0 },
    env: { ...notificationDatabase, DISCORD_WEBHOOK_URL: { preserveExisting: true, defaultValue: "", isOptional: true } },
  });
  return project(ctx.projectName ?? "boVIE", {
    resources: [mysqlData, natsData, mysql, nats, businessFrance, wttj, setup, relayBf, relayWttj, intake, delivery],
  });
});
