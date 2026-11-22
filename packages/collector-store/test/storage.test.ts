import { describe, expect, test } from "bun:test";
import { formatUtcDateTime, type RowDataPacket } from "@bovie/mysql-common";
import { contentHash } from "@bovie/offer-events";
import { createTestDbContext, getMysqlAdminUrl, makeEvent } from "@bovie/test-support";
import { recordPage, seen, upgrade as upgradeCollector } from "../src/index.js";

describe("collector storage", () => {
  test.skipIf(!getMysqlAdminUrl())("recorded offers keep content hash and sightings", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      const discovered = makeEvent();
      await recordPage(pool, [discovered], [discovered.source_offer_id], "scan", 1);
      await recordPage(pool, [discovered, makeEvent("abc")], ["ABC", "abc"], "scan", 2);

      expect(await seen(pool, "ABC")).toBe(true);
      expect(await seen(pool, "abc")).toBe(true);

      const [[countRow]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM offers",
      );
      expect(Number(countRow?.count)).toBe(2);

      const [[offer]] = await pool.execute<RowDataPacket[]>(
        "SELECT event_id, content_hash, observed_at, last_seen_at FROM offers WHERE source_offer_id = ?",
        ["ABC"],
      );
      expect(offer?.event_id).toBe(discovered.event_id);
      expect(offer?.content_hash).toBe(contentHash(discovered.offer));
      expect(offer?.observed_at).toBe(formatUtcDateTime(discovered.observed_at));
      const firstSighting = String(offer?.last_seen_at);

      const [[checkpoint]] = await pool.execute<RowDataPacket[]>(
        "SELECT `offset` FROM checkpoints WHERE scan = ?",
        ["scan"],
      );
      expect(Number(checkpoint?.offset)).toBe(2);

      await recordPage(pool, [], ["ABC", "unrecorded"], "scan", 3);
      const [[refreshed]] = await pool.execute<RowDataPacket[]>(
        "SELECT last_seen_at FROM offers WHERE source_offer_id = ?",
        ["ABC"],
      );
      expect(String(refreshed?.last_seen_at) > firstSighting).toBe(true);
      expect(await seen(pool, "unrecorded")).toBe(false);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("failed page rolls back offers and checkpoint", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      function* brokenEvents() {
        yield makeEvent();
        throw new Error("interrupted");
      }

      await expect(recordPage(pool, brokenEvents(), [], "scan", 1)).rejects.toThrow("interrupted");
      const [[offers]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM offers");
      const [[checkpoints]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM checkpoints",
      );
      expect(Number(offers?.count)).toBe(0);
      expect(Number(checkpoints?.count)).toBe(0);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("concurrent recording keeps one offer", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      await Promise.all(
        Array.from({ length: 4 }, () => recordPage(pool, [makeEvent()], ["ABC"], "scan", 1)),
      );
      const [[offers]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM offers");
      expect(Number(offers?.count)).toBe(1);
    } finally {
      await ctx.cleanup();
    }
  });
});
