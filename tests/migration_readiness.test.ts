import { describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { upgrade as upgradeCollector } from "@bovie/collector-store";
import { upgrade as upgradeDiscord } from "@bovie/discord-store";
import {
  type DbPool,
  makePool,
  type PoolConnection,
  type RowDataPacket,
} from "@bovie/mysql-common";
import { parseDatabaseUrl } from "@bovie/mysql-common/env";
import { upgradeSchema, waitForDatabase } from "@bovie/mysql-common/migrate";
import { getMysqlAdminUrl, withMysqlAdmin } from "./helpers/db.js";

describe("migration readiness and alembic adoption", () => {
  test.skipIf(!getMysqlAdminUrl())(
    "migration creates a missing database with hyphenated name",
    async () => {
      const name = `bovie-test-${randomUUID().replace(/-/g, "")}`;
      const adminConfig = parseDatabaseUrl(getMysqlAdminUrl()!);

      await withMysqlAdmin(async (admin) => {
        try {
          const pool = makePool({ ...adminConfig, database: name });
          const started = performance.now();
          try {
            await upgradeCollector(pool, { waitTimeout: 20 });
          } finally {
            await pool.close();
          }
          expect((performance.now() - started) / 1000).toBeLessThan(20);

          const [[schema]] = await admin.execute<RowDataPacket[]>(
            "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = ?",
            [name],
          );
          expect(schema?.DEFAULT_CHARACTER_SET_NAME).toBe("utf8mb4");
          expect(schema?.DEFAULT_COLLATION_NAME).toBe("utf8mb4_0900_bin");

          const [[offers]] = await admin.query<RowDataPacket[]>(
            `SELECT COUNT(*) AS count FROM \`${name}\`.offers`,
          );
          expect(Number(offers?.count)).toBe(0);
        } finally {
          await admin.query(`DROP DATABASE IF EXISTS \`${name}\``);
        }
      });
    },
  );

  test.skipIf(!getMysqlAdminUrl())(
    "adopts existing Alembic-migrated production databases cleanly",
    async () => {
      const collectorDb = `bovie_alembic_c_${randomUUID().replace(/-/g, "")}`;
      const discordDb = `bovie_alembic_d_${randomUUID().replace(/-/g, "")}`;
      const adminConfig = parseDatabaseUrl(getMysqlAdminUrl()!);

      await withMysqlAdmin(async (admin) => {
        try {
          // Simulate an existing Railway collector database created by Python Alembic.
          await admin.query(
            `CREATE DATABASE \`${collectorDb}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin`,
          );
          await admin.query(
            `CREATE TABLE \`${collectorDb}\`.alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)`,
          );
          await admin.query(
            `INSERT INTO \`${collectorDb}\`.alembic_version VALUES ('collector_store_0002')`,
          );
          await admin.query(`
          CREATE TABLE \`${collectorDb}\`.offers (
            source_offer_id VARCHAR(255) NOT NULL PRIMARY KEY,
            observed_at DATETIME(6) NOT NULL,
            event_id VARCHAR(36) NOT NULL UNIQUE,
            payload JSON NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            last_seen_at DATETIME(6) NOT NULL
          ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
        `);
          await admin.query(`
          CREATE TABLE \`${collectorDb}\`.checkpoints (
            scan VARCHAR(64) NOT NULL PRIMARY KEY,
            \`offset\` INT NOT NULL,
            results_seen_at DATETIME(6) NULL
          ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
        `);

          // Simulate an existing Railway discord database created by Python Alembic.
          await admin.query(
            `CREATE DATABASE \`${discordDb}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin`,
          );
          await admin.query(
            `CREATE TABLE \`${discordDb}\`.alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)`,
          );
          await admin.query(
            `INSERT INTO \`${discordDb}\`.alembic_version VALUES ('discord_store_0001')`,
          );
          await admin.query(`
          CREATE TABLE \`${discordDb}\`.inbox (
            event_id VARCHAR(36) NOT NULL PRIMARY KEY,
            payload JSON NOT NULL,
            received_at DATETIME(6) NOT NULL
          ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
        `);
          await admin.query(`
          CREATE TABLE \`${discordDb}\`.deliveries (
            event_id VARCHAR(36) NOT NULL PRIMARY KEY,
            payload JSON NOT NULL,
            attempts INT NOT NULL,
            available_at DATETIME(6) NOT NULL,
            claim_token VARCHAR(36) NULL,
            lease_until DATETIME(6) NULL,
            completed_at DATETIME(6) NULL
          ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
        `);

          const cPool = makePool({ ...adminConfig, database: collectorDb });
          const dPool = makePool({ ...adminConfig, database: discordDb });
          try {
            await upgradeCollector(cPool);
            await upgradeDiscord(dPool);
            const [cRows] = await cPool.query<RowDataPacket[]>(
              "SELECT version FROM schema_migrations ORDER BY version",
            );
            expect(cRows.map((r) => r.version)).toEqual([
              "collector_store_0001",
              "collector_store_0002",
            ]);
            const [dRows] = await dPool.query<RowDataPacket[]>(
              "SELECT version FROM schema_migrations ORDER BY version",
            );
            expect(dRows.map((r) => r.version)).toEqual(["discord_store_0001"]);
          } finally {
            await cPool.close();
            await dPool.close();
          }
        } finally {
          await admin.query(`DROP DATABASE IF EXISTS \`${collectorDb}\``);
          await admin.query(`DROP DATABASE IF EXISTS \`${discordDb}\``);
        }
      });
    },
  );

  test("database readiness retries connection failures", async () => {
    const fakeConn = {} as PoolConnection;
    let calls = 0;
    const sleeps: number[] = [];
    const pool = {
      async getConnection() {
        calls += 1;
        if (calls === 1) {
          throw new Error("ECONNREFUSED");
        }
        return fakeConn;
      },
    };

    const conn = await waitForDatabase(pool, 10, {
      monotonic: () => 0,
      sleep: async (s) => {
        sleeps.push(s);
      },
    });
    expect(conn).toBe(fakeConn);
    expect(calls).toBe(2);
    expect(sleeps).toEqual([2]);
  });

  test("database readiness deadline is bounded", async () => {
    let calls = 0;
    const sleeps: number[] = [];
    const times = [0, 2, 3];
    let timeIdx = 0;
    const pool = {
      async getConnection(): Promise<PoolConnection> {
        calls += 1;
        throw new Error("ECONNREFUSED");
      },
    };

    await expect(
      waitForDatabase(pool, 3, {
        monotonic: () => times[timeIdx++] ?? 3,
        sleep: async (s) => {
          sleeps.push(s);
        },
      }),
    ).rejects.toThrow("ECONNREFUSED");
    expect(calls).toBe(2);
    expect(sleeps).toEqual([1]);
  });

  test("migration errors are not retried", async () => {
    let getConnCalls = 0;
    let upCalls = 0;
    const fakeConn = {
      query: async () => [[], []],
      execute: async () => [[], []],
      release: () => {},
    } as unknown as PoolConnection;

    const pool = {
      config: { host: "localhost", port: 3306, user: "u", password: "p", database: "db" },
      async getConnection() {
        getConnCalls += 1;
        return fakeConn;
      },
    } as unknown as DbPool;

    await expect(
      upgradeSchema(
        pool,
        [
          {
            version: "broken",
            async up() {
              upCalls += 1;
              throw new Error("DDL error");
            },
          },
        ],
        { waitTimeout: 10 },
      ),
    ).rejects.toThrow("DDL error");
    expect(getConnCalls).toBe(1);
    expect(upCalls).toBe(1);
  });
});
