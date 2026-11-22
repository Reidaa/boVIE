import { randomUUID } from "node:crypto";
import { type DbPool, makePool } from "@bovie/mysql-common";
import { parseDatabaseUrl } from "@bovie/mysql-common/env";
import { createOfferEvent, type OfferEvent, type OfferEventInput } from "@bovie/offer-events";
import mysql, { type Connection } from "mysql2/promise";

export function getMysqlAdminUrl(): string | null {
  return process.env.MYSQL_TEST_ADMIN_URL ?? null;
}

export function getNatsTestUrl(): string | null {
  return process.env.NATS_TEST_URL ?? null;
}

export function getNatsAuthTestUrl(): string | null {
  return process.env.NATS_AUTH_TEST_URL ?? null;
}

export async function withMysqlAdmin<T>(fn: (admin: Connection) => Promise<T>): Promise<T> {
  const url = getMysqlAdminUrl();
  if (!url) {
    throw new Error("MYSQL_TEST_ADMIN_URL is not set");
  }
  const config = parseDatabaseUrl(url);
  const admin = await mysql.createConnection({
    host: config.host,
    port: config.port,
    user: config.user,
    password: config.password,
    database: config.database,
    charset: "utf8mb4",
    timezone: "Z",
  });
  try {
    return await fn(admin);
  } finally {
    await admin.end();
  }
}

/**
 * Disposable MySQL databases for one test.
 *
 * `create(upgrade)` makes an empty database and runs the schema upgrade of the
 * store under test, e.g. `ctx.create(upgrade)` with collector-store's `upgrade`.
 * `cleanup()` drops every database the context created.
 */
export interface TestDbContext {
  create(upgrade: (pool: DbPool) => Promise<void>): Promise<DbPool>;
  cleanup(): Promise<void>;
}

export async function createTestDbContext(): Promise<TestDbContext> {
  const url = getMysqlAdminUrl();
  if (!url) {
    throw new Error("MYSQL_TEST_ADMIN_URL is not set");
  }
  const config = parseDatabaseUrl(url);
  const admin = await mysql.createConnection({
    host: config.host,
    port: config.port,
    user: config.user,
    password: config.password,
    database: config.database,
    charset: "utf8mb4",
    timezone: "Z",
  });
  const created: Array<{ name: string; pool: DbPool }> = [];

  return {
    async create(upgrade: (pool: DbPool) => Promise<void>): Promise<DbPool> {
      const name = `bovie_test_${randomUUID().replace(/-/g, "")}`;
      await admin.query(`CREATE DATABASE \`${name}\` CHARACTER SET utf8mb4`);
      const pool = makePool({ ...config, database: name });
      created.push({ name, pool });
      await upgrade(pool);
      return pool;
    },
    async cleanup(): Promise<void> {
      try {
        for (const entry of created) {
          await entry.pool.close();
          await admin.query(`DROP DATABASE IF EXISTS \`${entry.name}\``);
        }
      } finally {
        await admin.end();
      }
    },
  };
}

export function makeEvent(offerId = "ABC", changes: Partial<OfferEventInput> = {}): OfferEvent {
  return createOfferEvent({
    type: "discovered",
    source: "business_france",
    source_offer_id: offerId,
    observed_at: new Date().toISOString(),
    offer: {
      title: "Engineer",
      organization: "Example",
      country: "France",
      city: "Paris",
      url: "https://example.com/jobs/abc",
      fields: [],
    },
    ...changes,
  });
}

export function jsonResponse(
  body: unknown,
  status = 200,
  headers?: Record<string, string>,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export { isolateProcess, stubPool, stubPublisher } from "./cli.js";
