import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { credentials, missingCredentials } from "./secrets.ts";

const cli = fileURLToPath(new URL("node_modules/.bin/railway", import.meta.url));
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
const deliveryVariables = services.some((service) => service.name === "discord-delivery")
  ? read(["variable", "list", "--service", "discord-delivery", "--json"])
  : {};
if (!Object.hasOwn(deliveryVariables, "DISCORD_WEBHOOK_URL")) {
  bootstrap["discord-delivery"] = { DISCORD_WEBHOOK_URL: "" };
}
const result = spawnSync(cli, ["config", action, ...process.argv.slice(3)], {
  stdio: "inherit",
  env: { ...process.env, _: cli, BOVIE_RAILWAY_BOOTSTRAP_SECRETS: JSON.stringify(bootstrap) },
});
process.exit(result.status ?? 1);
