import { config as dotenvConfig } from "dotenv";

export interface DatabaseUrlConfig {
  readonly host: string;
  readonly port: number;
  readonly user: string;
  readonly password: string;
  readonly database: string;
}

export class Env {
  readonly databaseUrl: DatabaseUrlConfig;

  constructor(input: { DATABASE_URL: string }) {
    this.databaseUrl = parseDatabaseUrl(input.DATABASE_URL);
  }

  toString(): string {
    const { user, host, port, database } = this.databaseUrl;
    return `Env(DATABASE_URL=mysql://${user}:***@${host}:${port}/${database})`;
  }

  [Symbol.for("nodejs.util.inspect.custom")](): string {
    return this.toString();
  }
}

export function parseDatabaseUrl(raw: string): DatabaseUrlConfig {
  if (!raw || typeof raw !== "string") {
    throw new Error("DATABASE_URL must be a MySQL URL");
  }
  let normalized = raw;
  if (normalized.startsWith("mysql+pymysql://")) {
    normalized = `mysql://${normalized.slice("mysql+pymysql://".length)}`;
  }
  let parsed: URL;
  try {
    parsed = new URL(normalized);
  } catch {
    throw new Error("DATABASE_URL must be a MySQL URL");
  }
  if (parsed.protocol !== "mysql:") {
    throw new Error("Use mysql://user:password@host/database");
  }
  const host = parsed.hostname;
  const user = decodeURIComponent(parsed.username);
  const password = decodeURIComponent(parsed.password);
  const database = decodeURIComponent(parsed.pathname.replace(/^\//, ""));
  if (!host || !user || !database) {
    throw new Error("Use mysql://user:password@host/database");
  }
  let port = 3306;
  if (parsed.port) {
    port = Number(parsed.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new Error("DATABASE_URL must be a MySQL URL");
    }
  }
  return { host, port, user, password, database };
}

export function loadEnv(): Env {
  dotenvConfig({ path: ".env", override: false, quiet: true });
  return new Env({ DATABASE_URL: process.env.DATABASE_URL ?? "" });
}
