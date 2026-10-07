import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { credentials, missingCredentials } from "./secrets.ts";

// npm workspaces hoist the CLI to the repository root unless a version conflict keeps it local.
const cli = (() => {
  const found = ["node_modules/.bin/railway", "../../node_modules/.bin/railway"]
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

const action = process.argv[2];
if (action !== "plan" && action !== "apply") throw new Error("Expected plan or apply.");
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
  bootstrap["discord-sender"] = { DISCORD_WEBHOOK_URL: "" };
}
// The CLI only finds `.railway/railway.ts` on its own; this workspace keeps it in infra/railway.
const file = fileURLToPath(new URL("railway.ts", import.meta.url));
const result = spawnSync(cli, ["config", action, "--file", file, ...process.argv.slice(3)], {
  stdio: "inherit",
  env: { ...process.env, _: cli, BOVIE_RAILWAY_BOOTSTRAP_SECRETS: JSON.stringify(bootstrap) },
});
process.exit(result.status ?? 1);
