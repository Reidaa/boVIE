import { randomBytes } from "node:crypto";

export const credentials = {
  mysql: ["MYSQL_ROOT_PASSWORD", "BF_DATABASE_PASSWORD", "WTTJ_DATABASE_PASSWORD", "NOTIFICATION_DATABASE_PASSWORD"],
  nats: ["NATS_ADMIN_PASSWORD", "NATS_BF_PASSWORD", "NATS_WTTJ_PASSWORD", "NATS_NOTIFICATIONS_PASSWORD"],
};

export function missingCredentials(owner: keyof typeof credentials, existing: Record<string, unknown>) {
  return Object.fromEntries(credentials[owner]
    // Null can represent a sealed variable. Only absent or empty values need a password.
    .filter((key) => !Object.hasOwn(existing, key) || existing[key] === "")
    .map((key) => [key, randomBytes(32).toString("hex")]));
}
