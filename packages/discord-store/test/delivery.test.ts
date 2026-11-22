import { describe, expect, test } from "bun:test";
import type { RowDataPacket } from "@bovie/mysql-common";
import { claim, finish, retryLater } from "@bovie/mysql-common/queue";
import { createTestDbContext, getMysqlAdminUrl, makeEvent } from "@bovie/test-support";
import { accept, DELIVERIES_TABLE, upgrade as upgradeDiscord } from "../src/index.js";

describe("discord store delivery and leases", () => {
  test.skipIf(!getMysqlAdminUrl())("duplicate ingestion creates one pending delivery", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeDiscord);
      const discovered = makeEvent();
      expect(await accept(pool, discovered)).toBe(true);
      expect(await accept(pool, discovered)).toBe(false);

      const [[inbox]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM inbox");
      const [[deliveries]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM deliveries",
      );
      expect(Number(inbox?.count)).toBe(1);
      expect(Number(deliveries?.count)).toBe(1);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("reused event ID for another offer is rejected", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeDiscord);
      const discovered = makeEvent();
      await accept(pool, discovered);
      await expect(accept(pool, { ...discovered, source_offer_id: "other" })).rejects.toThrow(
        /different offer/,
      );
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("republished event is accepted once", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeDiscord);
      expect(await accept(pool, makeEvent())).toBe(true);
      const later = new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString();
      expect(await accept(pool, makeEvent("ABC", { observed_at: later }))).toBe(false);

      const [[inbox]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM inbox");
      const [[deliveries]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM deliveries",
      );
      expect(Number(inbox?.count)).toBe(1);
      expect(Number(deliveries?.count)).toBe(1);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("only discoveries create deliveries", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeDiscord);
      expect(await accept(pool, makeEvent("ABC", { type: "updated" }))).toBe(false);
      expect(await accept(pool, makeEvent("ABC", { type: "closed" }))).toBe(false);

      const [[inbox]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM inbox");
      const [[deliveries]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM deliveries",
      );
      expect(Number(inbox?.count)).toBe(2);
      expect(Number(deliveries?.count)).toBe(0);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("lease expiry and stale completion", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeDiscord);
      await accept(pool, makeEvent());
      const now = new Date(Date.now() + 1000);
      const first = await claim(pool, DELIVERIES_TABLE, { now, leaseSeconds: 10 });
      expect(first).not.toBeNull();
      expect(await claim(pool, DELIVERIES_TABLE, { now })).toBeNull();

      const later = new Date(now.getTime() + 11_000);
      const second = await claim(pool, DELIVERIES_TABLE, { now: later });
      expect(second).not.toBeNull();
      expect(first!.token).not.toBe(second!.token);
      expect(await finish(pool, DELIVERIES_TABLE, first!, { now: later })).toBe(false);
      expect(await finish(pool, DELIVERIES_TABLE, second!, { now: later })).toBe(true);
      expect(await claim(pool, DELIVERIES_TABLE, { now: later })).toBeNull();
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("failed delivery remains pending with backoff", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeDiscord);
      await accept(pool, makeEvent());
      const now = new Date(Date.now() + 1000);
      const first = await claim(pool, DELIVERIES_TABLE, { now });
      expect(first).not.toBeNull();
      expect(await retryLater(pool, DELIVERIES_TABLE, first!, { now })).toBe(true);
      expect(await claim(pool, DELIVERIES_TABLE, { now })).toBeNull();

      const later = new Date(now.getTime() + 61_000);
      const second = await claim(pool, DELIVERIES_TABLE, { now: later });
      expect(second).not.toBeNull();
      expect(second!.attempts).toBe(2);
      expect(await finish(pool, DELIVERIES_TABLE, second!, { now: later })).toBe(true);
    } finally {
      await ctx.cleanup();
    }
  });
});
