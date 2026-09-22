import { randomBytes } from "node:crypto";

export const credentials = {
  nats: ["NATS_ADMIN_PASSWORD", "NATS_BF_PASSWORD", "NATS_WTTJ_PASSWORD", "NATS_NOTIFICATIONS_PASSWORD"],
};

export function missingCredentials(owner: keyof typeof credentials, existing: Record<string, unknown>) {
  return Object.fromEntries(credentials[owner]
    // Null can represent a sealed variable. Only absent or empty values need a password.
    .filter((key) => !Object.hasOwn(existing, key) || existing[key] === "")
    // NATS parses digit-leading environment values as numbers.
    .map((key) => [key, `bovie_${randomBytes(32).toString("hex")}`]));
}
