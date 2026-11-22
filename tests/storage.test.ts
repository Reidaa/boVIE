import { describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { inspect } from "node:util";
import { recordPage, seen } from "@bovie/collector-store";
import { formatUtcDateTime, makePool, type RowDataPacket } from "@bovie/mysql-common";
import { Env, parseDatabaseUrl } from "@bovie/mysql-common/env";
import { contentHash } from "@bovie/offer-events";
import mysql from "mysql2/promise";
import { createTestDbContext, getMysqlAdminUrl, makeEvent } from "./helpers/db.js";

describe("storage and mysql configuration", () => {
  test("MySQL URL validation and password redaction", () => {
    const settings = new Env({ DATABASE_URL: "mysql+pymysql://worker:secret@localhost/source" });
    expect(settings.databaseUrl.user).toBe("worker");
    expect(settings.databaseUrl.database).toBe("source");
    expect(inspect(settings)).not.toContain("secret");
    expect(String(settings)).not.toContain("secret");

    const railway = new Env({ DATABASE_URL: "mysql://worker:p%40ss@localhost/source" });
    expect(railway.databaseUrl.password).toBe("p@ss");

    for (const url of [
      "postgresql://u:p@host/db",
      "sqlite://",
      "mysql://u:p@host",
      "not a url",
      "mysql://u:p@host:port/db",
    ]) {
      expect(() => new Env({ DATABASE_URL: url })).toThrow();
    }
  });

  test("imports do not open a database connection", () => {
    const cleanEnv = { ...process.env };
    delete cleanEnv.DATABASE_URL;
    execFileSync(
      "bun",
      [
        "-e",
        `
        import mysql from "mysql2/promise";
        mysql.createPool = () => { throw new Error("Import attempted to create a pool"); };
        mysql.createConnection = () => { throw new Error("Import attempted to create a connection"); };
        await import("@bovie/mysql-common/env");
        await import("@bovie/mysql-common");
        await import("@bovie/collector-business-france");
      `,
      ],
      { env: cleanEnv, stdio: "pipe" },
    );
  });

  test("event IDs are stable across republishing", () => {
    const first = makeEvent();
    expect(makeEvent().event_id).toBe(first.event_id);
    expect(makeEvent("ABC", { observed_at: "2026-01-01T00:00:00Z" }).event_id).toBe(first.event_id);
    expect(makeEvent("other").event_id).not.toBe(first.event_id);
    expect(makeEvent("ABC", { type: "closed" }).event_id).not.toBe(first.event_id);
    expect(makeEvent("ABC", { source: "wttj" }).event_id).not.toBe(first.event_id);
  });

  test("update event IDs follow offer content", () => {
    const update = makeEvent("ABC", { type: "updated" });
    expect(makeEvent("ABC", { type: "updated" }).event_id).toBe(update.event_id);
    const changed = makeEvent("ABC", {
      type: "updated",
      offer: { ...update.offer, title: "Lead" },
    });
    expect(changed.event_id).not.toBe(update.event_id);
  });

  test.skipIf(!getMysqlAdminUrl())("recorded offers keep content hash and sightings", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("collector");
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
      const pool = await ctx.create("collector");
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
      const pool = await ctx.create("collector");
      await Promise.all(
        Array.from({ length: 4 }, () => recordPage(pool, [makeEvent()], ["ABC"], "scan", 1)),
      );
      const [[offers]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM offers");
      expect(Number(offers?.count)).toBe(1);
    } finally {
      await ctx.cleanup();
    }
  });

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
            { pool: await ctx.create("collector"), table: "offers" },
            { pool: await ctx.create("collector"), table: "offers" },
            { pool: await ctx.create("discord"), table: "inbox" },
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
