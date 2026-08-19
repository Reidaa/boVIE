import { database, defineRailway, github, preserve, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const postgres = database("Postgres-jNxP", "postgres", {
    image: "ghcr.io/railwayapp-templates/postgres-ssl:17",
    output: "DATABASE_URL",
    defaultMountPath: "/var/lib/postgresql/data",
    region: "europe-west4-drams3a",
  });

  const databaseVolume = volume("postgres-jnxp-volume", {
    alerts: { usage: { "80": {}, "95": {}, "100": {} } },
    allowOnlineResize: true,
    region: "europe-west4-drams3a",
    sizeMB: 50000,
  });

  const app = service("bovie", {
    source: github("Reidaa/boVIE", { checkSuites: false }),
    build: {
      builder: "RAILPACK",
      buildCommand: "uv sync --frozen --no-dev",
      watchPatterns: ["src/bovie/**", "uv.lock", "pyproject.toml", ".python-version"],
    },
    deploy: {
      startCommand: "python3 -m bovie.main",
      cronSchedule: "12 */2 * * *",
      restartPolicyType: "NEVER",
    },
    replicas: { "europe-west4-drams3a": 1 },
    networking: { privateNetworkEndpoint: "service" },
    env: {
      BOVIE_DEBUG: preserve(),
      BOVIE_LIMIT: preserve(),
      BOVIE_REGION: preserve(),
      BOVIE_SPECIALIZATION: preserve(),
      DATABASE_URL: postgres.env.DATABASE_URL,
      DISCORD_WEBHOOK_URL: preserve(),
    },
  });

  return project("boVIE", {
    resources: [postgres, databaseVolume, app],
  });
});
