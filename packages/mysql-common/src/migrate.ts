import mysql, { type PoolConnection, type RowDataPacket } from "mysql2/promise";
import type { DbPool } from "./index.js";
import { utcNowString } from "./index.js";

// MySQL error for a database that does not exist. The server answered, so it is ready.
export const UNKNOWN_DATABASE = 1049;

export interface Migration {
  readonly version: string;
  readonly legacyAlembicRevisions?: readonly string[];
  up(conn: PoolConnection): Promise<void>;
}

export interface WaitDeps {
  monotonic?: () => number;
  sleep?: (seconds: number) => Promise<void>;
}

const defaultMonotonic = (): number => performance.now() / 1000;
const defaultSleep = (seconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, Math.max(0, seconds * 1000)));

export function isUnknownDatabaseError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }
  const err = error as { errno?: number; code?: string };
  return err.errno === UNKNOWN_DATABASE || err.code === "ER_BAD_DB_ERROR";
}

function quoteIdentifier(name: string): string {
  return `\`${name.replace(/`/g, "``")}\``;
}

/**
 * Connect, retrying until the server answers or `timeout` seconds pass.
 *
 * A missing database means the server is up; that error is thrown at once.
 */
export async function waitForDatabase(
  pool: Pick<DbPool, "getConnection">,
  timeoutSeconds: number,
  deps: WaitDeps = {},
): Promise<PoolConnection> {
  const monotonic = deps.monotonic ?? defaultMonotonic;
  const sleep = deps.sleep ?? defaultSleep;
  const deadline = monotonic() + timeoutSeconds;

  while (true) {
    try {
      return await pool.getConnection();
    } catch (error) {
      const remaining = deadline - monotonic();
      if (isUnknownDatabaseError(error) || remaining <= 0) {
        throw error;
      }
      await sleep(Math.min(2, remaining));
    }
  }
}

/**
 * Create the database named in the pool config, with the collation of local Compose.
 */
export async function createDatabase(pool: Pick<DbPool, "config">): Promise<void> {
  const name = pool.config.database;
  if (!name) {
    throw new Error("The database URL names no database");
  }
  const server = await mysql.createConnection({
    host: pool.config.host,
    port: pool.config.port,
    user: pool.config.user,
    password: pool.config.password,
    charset: "utf8mb4",
    timezone: "Z",
    connectTimeout: 10_000,
  });
  try {
    await server.query(
      `CREATE DATABASE IF NOT EXISTS ${quoteIdentifier(name)} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin`,
    );
  } finally {
    await server.end();
  }
}

async function connectOrCreateDatabase(
  pool: DbPool,
  waitTimeout: number,
  deps: WaitDeps,
): Promise<PoolConnection> {
  try {
    return await waitForDatabase(pool, waitTimeout, deps);
  } catch (error) {
    if (!isUnknownDatabaseError(error)) {
      throw error;
    }
  }
  await createDatabase(pool);
  return await pool.getConnection();
}

async function readLegacyAlembicRevisions(conn: PoolConnection): Promise<Set<string>> {
  const [tables] = await conn.query<RowDataPacket[]>(
    "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'alembic_version'",
  );
  if (tables.length === 0) {
    return new Set();
  }
  const [rows] = await conn.query<RowDataPacket[]>("SELECT version_num FROM alembic_version");
  return new Set(rows.map((row) => String(row.version_num)));
}

/**
 * Migrate to head. Creates the database in the URL first when it is missing.
 *
 * Adopts existing Alembic revisions into `schema_migrations` so production
 * databases migrated by Python Alembic upgrade cleanly without re-creating tables.
 */
export async function upgradeSchema(
  pool: DbPool,
  migrations: readonly Migration[],
  options: { waitTimeout?: number; deps?: WaitDeps } = {},
): Promise<void> {
  const waitTimeout = options.waitTimeout ?? 0;
  const conn = await connectOrCreateDatabase(pool, waitTimeout, options.deps ?? {});
  try {
    await conn.query(
      `CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(128) NOT NULL,
        applied_at DATETIME(6) NOT NULL,
        PRIMARY KEY (version)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin`,
    );

    const legacyRevisions = await readLegacyAlembicRevisions(conn);
    if (legacyRevisions.size > 0) {
      const adoptedAt = utcNowString();
      for (const migration of migrations) {
        if (migration.legacyAlembicRevisions?.some((rev) => legacyRevisions.has(rev))) {
          await conn.execute(
            "INSERT IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            [migration.version, adoptedAt],
          );
        }
      }
    }

    const [appliedRows] = await conn.query<RowDataPacket[]>(
      "SELECT version FROM schema_migrations",
    );
    const applied = new Set(appliedRows.map((row) => String(row.version)));

    for (const migration of migrations) {
      if (applied.has(migration.version)) {
        continue;
      }
      await migration.up(conn);
      await conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", [
        migration.version,
        utcNowString(),
      ]);
    }
  } finally {
    conn.release();
  }
}
