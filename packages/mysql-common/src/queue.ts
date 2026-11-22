import { randomUUID } from "node:crypto";
import type { PoolConnection, ResultSetHeader, RowDataPacket } from "mysql2/promise";
import { addSecondsToUtcString, type DbPool, formatUtcDateTime } from "./index.js";

export interface Claim {
  readonly eventId: string;
  readonly token: string;
  readonly payload: Record<string, unknown>;
  readonly attempts: number;
}

const VALID_TABLE = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

function assertTableName(table: string): string {
  if (!VALID_TABLE.test(table)) {
    throw new Error(`Invalid queue table name: ${table}`);
  }
  return `\`${table}\``;
}

export async function databaseNow(conn: PoolConnection): Promise<string> {
  const [rows] = await conn.query<RowDataPacket[]>(
    "SELECT DATE_FORMAT(UTC_TIMESTAMP(6), '%Y-%m-%d %H:%i:%s.%f') AS now_utc",
  );
  const first = rows[0];
  if (!first || typeof first.now_utc !== "string") {
    throw new Error("Failed to read UTC_TIMESTAMP(6) from MySQL");
  }
  return first.now_utc;
}

function parseJsonColumn(value: unknown): Record<string, unknown> {
  if (typeof value === "string") {
    return JSON.parse(value) as Record<string, unknown>;
  }
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  throw new Error("Unexpected payload column value");
}

export async function claim(
  pool: DbPool,
  table: string,
  options: { now?: Date | string; leaseSeconds?: number } = {},
): Promise<Claim | null> {
  const quoted = assertTableName(table);
  const leaseSeconds = options.leaseSeconds ?? 120;

  return await pool.withTransaction(async (conn) => {
    const now = options.now ? formatUtcDateTime(options.now) : await databaseNow(conn);
    const [rows] = await conn.execute<RowDataPacket[]>(
      `SELECT event_id, payload, attempts
       FROM ${quoted}
       WHERE completed_at IS NULL
         AND available_at <= ?
         AND (lease_until IS NULL OR lease_until <= ?)
       ORDER BY available_at, event_id
       LIMIT 1
       FOR UPDATE SKIP LOCKED`,
      [now, now],
    );
    const row = rows[0];
    if (!row) {
      return null;
    }
    const token = randomUUID();
    const leaseUntil = addSecondsToUtcString(now, leaseSeconds);
    const attempts = Number(row.attempts) + 1;
    await conn.execute(
      `UPDATE ${quoted}
       SET claim_token = ?, lease_until = ?, attempts = ?
       WHERE event_id = ?`,
      [token, leaseUntil, attempts, String(row.event_id)],
    );
    return {
      eventId: String(row.event_id),
      token,
      payload: parseJsonColumn(row.payload),
      attempts,
    };
  });
}

export async function finish(
  pool: DbPool,
  table: string,
  work: Claim,
  options: { now?: Date | string } = {},
): Promise<boolean> {
  const quoted = assertTableName(table);
  return await pool.withTransaction(async (conn) => {
    const now = options.now ? formatUtcDateTime(options.now) : await databaseNow(conn);
    const [result] = await conn.execute<ResultSetHeader>(
      `UPDATE ${quoted}
       SET completed_at = ?, claim_token = NULL, lease_until = NULL
       WHERE event_id = ?
         AND claim_token = ?
         AND completed_at IS NULL
         AND lease_until > ?`,
      [now, work.eventId, work.token, now],
    );
    return result.affectedRows === 1;
  });
}

export async function retryLater(
  pool: DbPool,
  table: string,
  work: Claim,
  options: { now?: Date | string; delaySeconds?: number } = {},
): Promise<boolean> {
  const quoted = assertTableName(table);
  const delay =
    options.delaySeconds !== undefined
      ? options.delaySeconds
      : Math.min(3600, 5 * 2 ** Math.min(work.attempts, 10));

  return await pool.withTransaction(async (conn) => {
    const now = options.now ? formatUtcDateTime(options.now) : await databaseNow(conn);
    const availableAt = addSecondsToUtcString(now, delay);
    const [result] = await conn.execute<ResultSetHeader>(
      `UPDATE ${quoted}
       SET available_at = ?, claim_token = NULL, lease_until = NULL
       WHERE event_id = ?
         AND claim_token = ?
         AND completed_at IS NULL
         AND lease_until > ?`,
      [availableAt, work.eventId, work.token, now],
    );
    return result.affectedRows === 1;
  });
}
