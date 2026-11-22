import { describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { upgrade as upgradeCollector } from "@bovie/collector-store";
import { upgrade as upgradeDiscord } from "@bovie/discord-store";
import { makePool, type RowDataPacket } from "@bovie/mysql-common";
import { parseDatabaseUrl } from "@bovie/mysql-common/env";
import { createTestDbContext, getMysqlAdminUrl } from "@bovie/test-support";
import mysql from "mysql2/promise";

describe("database domain isolation", () => {
  for (const owner of [0, 1, 2]) {
    test.skipIf(!getMysqlAdminUrl())(
      `domain credentials cannot access other domains (owner ${owner})`,
      async () => {
        const ctx = await createTestDbContext();
        const adminUrl = getMysqlAdminUrl()!;
        const adminConfig = parseDatabaseUrl(adminUrl);
        const admin = await mysql.createConnection({
          host: adminConfig.host,
          port: adminConfig.port,
          user: adminConfig.user,
          password: adminConfig.password,
          database: "mysql",
        });
        const user = `bovie_test_${randomUUID().replace(/-/g, "").slice(0, 20)}`;
        const password = randomUUID().replace(/-/g, "");

        try {
          const domains = [
            { pool: await ctx.create(upgradeCollector), table: "offers" },
            { pool: await ctx.create(upgradeCollector), table: "offers" },
            { pool: await ctx.create(upgradeDiscord), table: "inbox" },
          ];
          const first = domains[owner]!;
          await admin.query("CREATE USER ? IDENTIFIED BY ?", [user, password]);
          await admin.query(`GRANT ALL ON \`${first.pool.config.database}\`.* TO ?`, [user]);

          const restricted = makePool({
            ...first.pool.config,
            user,
            password,
          });
          try {
            const [[ownCount]] = await restricted.query<RowDataPacket[]>(
              `SELECT COUNT(*) AS count FROM ${first.table}`,
            );
            expect(Number(ownCount?.count)).toBe(0);
            for (let index = 0; index < domains.length; index += 1) {
              if (index === owner) {
                continue;
              }
              const other = domains[index]!;
              await expect(
                restricted.query(`SELECT * FROM \`${other.pool.config.database}\`.${other.table}`),
              ).rejects.toThrow();
            }
          } finally {
            await restricted.close();
          }
        } finally {
          await admin.query("DROP USER IF EXISTS ?", [user]);
          await admin.end();
          await ctx.cleanup();
        }
      },
    );
  }
});
