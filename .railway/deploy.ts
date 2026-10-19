import { spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { credentials, missingCredentials } from "./secrets.ts";

// npm workspaces hoist the CLI to the repository root unless a version conflict keeps it local.
const cli = (() => {
  const found = ["node_modules/.bin/railway", "../node_modules/.bin/railway"]
    .map((path) => fileURLToPath(new URL(path, import.meta.url)))
    .find((path) => existsSync(path));
  if (!found) throw new Error("Railway CLI not found. Run npm ci at the repository root.");
  return found;
})();
function read(args: string[]) {
  const result = spawnSync(cli, args, { encoding: "utf8" });
  if (result.status !== 0)
    throw new Error(
      `Railway ${args.slice(0, 2).join(" ")} failed. Check login and project linkage.`,
    );
  return JSON.parse(result.stdout);
}

// `plan <environment>` saves the reviewed change set; `apply` lands exactly that file and
// never re-plans. The file pins its environment and can hold generated passwords.
// It stays outside .railway/, whose tree the plan pins.
const root = fileURLToPath(new URL("..", import.meta.url));
const savedPlan = `${root}railway-plan.json`;
const run = (args: string[], env: NodeJS.ProcessEnv = {}) =>
  spawnSync(cli, args, {
    // The CLI pins `.railway/` relative to its working directory.
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, _: cli, ...env },
  }).status ?? 1;

const [action, environment, ...extra] = process.argv.slice(2);
if (action === "apply") {
  const status = run(["config", "apply", "--plan", savedPlan, ...process.argv.slice(3)]);
  if (status === 0) rmSync(savedPlan);
  process.exit(status);
}
if (action !== "plan" || !environment) throw new Error("Expected plan <environment> or apply.");
// Config commands have no environment option; they use the directory's linked environment.
if (run(["environment", "link", environment]) !== 0) process.exit(1);
const services: { name: string }[] = read(["service", "list", "--json"]);
const bootstrap: Record<string, Record<string, string>> = {};
for (const owner of Object.keys(credentials) as (keyof typeof credentials)[]) {
  const existing = services.some((service) => service.name === owner)
    ? read(["variable", "list", "--service", owner, "--json"])
    : {};
  bootstrap[owner] = missingCredentials(owner, existing);
}
const deliveryVariables = services.some((service) => service.name === "discord-sender")
  ? read(["variable", "list", "--service", "discord-sender", "--json"])
  : {};
if (!Object.hasOwn(deliveryVariables, "DISCORD_WEBHOOK_URL")) {
  // A new environment takes its webhook from the shell that runs the plan.
  bootstrap["discord-sender"] = { DISCORD_WEBHOOK_URL: process.env.DISCORD_WEBHOOK_URL ?? "" };
}
process.exit(
  run(["config", "plan", "--out", savedPlan, ...extra], {
    BOVIE_RAILWAY_BOOTSTRAP_SECRETS: JSON.stringify(bootstrap),
  }),
);
