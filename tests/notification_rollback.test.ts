import { describe, expect, test } from "bun:test";
import { accept } from "@bovie/discord-store";
import type { RowDataPacket } from "@bovie/mysql-common";
import { createTestDbContext, getMysqlAdminUrl, makeEvent } from "./helpers/db.js";

describe("discord store atomic rollback", () => {
  test.skipIf(!getMysqlAdminUrl())("failed delivery insert rolls back inbox", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("discord");
      await pool.query(`
        CREATE TRIGGER fail_deliveries_insert
        BEFORE INSERT ON deliveries
        FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'injected failure before delivery insert'
      `);

      await expect(accept(pool, makeEvent())).rejects.toThrow(
        /injected failure before delivery insert/,
      );

      const [[deliveries]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM deliveries",
      );
      const [[inbox]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM inbox");
      expect(Number(deliveries?.count)).toBe(0);
      expect(Number(inbox?.count)).toBe(0);
    } finally {
      await ctx.cleanup();
    }
  });
});
