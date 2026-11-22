import mysql, {
  type Pool,
  type PoolConnection,
  type QueryResult,
  type ResultSetHeader,
  type RowDataPacket,
} from "mysql2/promise";
import type { DatabaseUrlConfig } from "./env.js";

export type { Pool, PoolConnection, QueryResult, ResultSetHeader, RowDataPacket };
export type { DatabaseUrlConfig } from "./env.js";

export type QueryParams = Parameters<Pool["query"]>[1];
export type ExecuteParams = Parameters<Pool["execute"]>[1];

export interface DbPool {
  readonly config: DatabaseUrlConfig;
  readonly pool: Pool;
  getConnection(): Promise<PoolConnection>;
  query<T extends QueryResult = RowDataPacket[]>(
    sql: string,
    params?: QueryParams,
  ): Promise<[T, unknown]>;
  execute<T extends QueryResult = RowDataPacket[]>(
    sql: string,
    params?: ExecuteParams,
  ): Promise<[T, unknown]>;
  withTransaction<T>(fn: (conn: PoolConnection) => Promise<T>): Promise<T>;
  close(): Promise<void>;
}

const AWARE_ISO = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})$/i;
const MYSQL_DATETIME = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?$/;

function dateToUtcMicrosString(date: Date, extraMicros = 0): string {
  const pad = (n: number, len = 2) => String(n).padStart(len, "0");
  const micros = date.getUTCMilliseconds() * 1000 + extraMicros;
  return (
    `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ` +
    `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}.` +
    `${pad(micros, 6)}`
  );
}

/**
 * Format a Date or timezone-aware ISO-8601 string into MySQL DATETIME(6) UTC string.
 */
export function formatUtcDateTime(value: Date | string): string {
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      throw new Error("Invalid Date");
    }
    return dateToUtcMicrosString(value);
  }
  const mysqlMatch = MYSQL_DATETIME.exec(value);
  if (mysqlMatch) {
    const frac = (mysqlMatch[3] ?? "").padEnd(6, "0").slice(0, 6);
    return `${mysqlMatch[1]} ${mysqlMatch[2]}.${frac}`;
  }
  const match = AWARE_ISO.exec(value);
  if (!match) {
    throw new Error("Timestamps must be timezone aware");
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("Invalid timestamp");
  }
  const fracRaw = (match[3] ?? "").padEnd(6, "0").slice(0, 6);
  const subMsMicros = Number.parseInt(fracRaw.slice(3, 6), 10);
  return dateToUtcMicrosString(parsed, subMsMicros);
}

/**
 * Parse a MySQL DATETIME(6) UTC string or Date into a UTC Date.
 */
export function parseUtcDateTime(value: string | Date): Date {
  if (value instanceof Date) {
    return value;
  }
  const match = MYSQL_DATETIME.exec(value);
  if (match) {
    const ms = (match[3] ?? "000").padEnd(3, "0").slice(0, 3);
    return new Date(`${match[1]}T${match[2]}.${ms}Z`);
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`Invalid UTC datetime: ${value}`);
  }
  return parsed;
}

let lastUtcMicros = 0;

/**
 * Current UTC timestamp formatted for DATETIME(6), strictly monotonic to the microsecond.
 */
export function utcNowString(): string {
  const nowMicros = Date.now() * 1000;
  lastUtcMicros = nowMicros > lastUtcMicros ? nowMicros : lastUtcMicros + 1;
  const ms = Math.floor(lastUtcMicros / 1000);
  const subMs = lastUtcMicros % 1000;
  return dateToUtcMicrosString(new Date(ms), subMs);
}

export function addSecondsToUtcString(utcStr: string, seconds: number): string {
  const normalized = formatUtcDateTime(utcStr);
  const match = MYSQL_DATETIME.exec(normalized);
  if (!match) {
    throw new Error(`Invalid UTC datetime: ${utcStr}`);
  }
  const frac = (match[3] ?? "000000").padEnd(6, "0");
  const baseMs = Date.parse(`${match[1]}T${match[2]}Z`);
  const baseMicros = baseMs * 1000 + Number.parseInt(frac, 10);
  const totalMicros = baseMicros + Math.round(seconds * 1_000_000);
  const targetMs = Math.floor(totalMicros / 1000);
  const subMs = ((totalMicros % 1000) + 1000) % 1000;
  return dateToUtcMicrosString(new Date(targetMs), subMs);
}

export function makePool(config: DatabaseUrlConfig): DbPool {
  const pool = mysql.createPool({
    host: config.host,
    port: config.port,
    user: config.user,
    password: config.password,
    database: config.database,
    charset: "utf8mb4",
    timezone: "Z",
    dateStrings: true,
    connectTimeout: 10_000,
    waitForConnections: true,
    connectionLimit: 10,
    enableKeepAlive: true,
  });

  return {
    config,
    pool,
    getConnection() {
      return pool.getConnection();
    },
    query<T extends QueryResult = RowDataPacket[]>(
      sql: string,
      params?: QueryParams,
    ): Promise<[T, unknown]> {
      return params !== undefined ? pool.query<T>(sql, params) : pool.query<T>(sql);
    },
    execute<T extends QueryResult = RowDataPacket[]>(
      sql: string,
      params?: ExecuteParams,
    ): Promise<[T, unknown]> {
      return params !== undefined ? pool.execute<T>(sql, params) : pool.execute<T>(sql);
    },
    async withTransaction<T>(fn: (conn: PoolConnection) => Promise<T>): Promise<T> {
      const conn = await pool.getConnection();
      try {
        await conn.beginTransaction();
        const result = await fn(conn);
        await conn.commit();
        return result;
      } catch (error) {
        await conn.rollback();
        throw error;
      } finally {
        conn.release();
      }
    },
    async close(): Promise<void> {
      await pool.end();
    },
  };
}
