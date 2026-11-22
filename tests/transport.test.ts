import { describe, expect, test } from "bun:test";
import { logger } from "@bovie/cli-common";
import { handle, receiveMessage, retryDelay } from "@bovie/discord-intake";
import { deliverOne, discordPayload, HttpStatusError } from "@bovie/discord-sender";
import { accept } from "@bovie/discord-store";
import {
  type DbPool,
  formatUtcDateTime,
  parseUtcDateTime,
  type RowDataPacket,
} from "@bovie/mysql-common";
import { type OfferSource, serializeOfferEvent } from "@bovie/offer-events";
import { createTestDbContext, getMysqlAdminUrl, jsonResponse, makeEvent } from "./helpers/db.js";

describe("intake and sender transport", () => {
  test.skipIf(!getMysqlAdminUrl())("receiver commit precedes ack", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("discord");
      const discovered = makeEvent();
      let acked = 0;

      const message = {
        subject: "offers.business_france.v1",
        data: Buffer.from(serializeOfferEvent(discovered), "utf8"),
        async ackAck() {
          const [[row]] = await pool.query<RowDataPacket[]>("SELECT event_id FROM deliveries");
          expect(row?.event_id).toBe(discovered.event_id);
          acked += 1;
          return true;
        },
      };

      await receiveMessage(pool, message);
      await receiveMessage(pool, message);
      expect(acked).toBe(2);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("discord outage then success", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("discord");
      const discovered = makeEvent();
      await accept(pool, discovered);

      const statuses = [503, 204];
      let idx = 0;
      const requests: string[] = [];

      const fetchFn = async (url: string) => {
        requests.push(url);
        return new Response(null, { status: statuses[idx++] });
      };

      await expect(
        deliverOne(pool, fetchFn, "https://discord.invalid/webhook"),
      ).rejects.toBeInstanceOf(HttpStatusError);

      const [[row]] = await pool.execute<RowDataPacket[]>(
        "SELECT completed_at FROM deliveries WHERE event_id = ?",
        [discovered.event_id],
      );
      expect(row?.completed_at).toBeNull();

      await pool.execute("UPDATE deliveries SET available_at = ?", [
        formatUtcDateTime(new Date(Date.now() - 1000)),
      ]);

      expect(await deliverOne(pool, fetchFn, "https://discord.invalid/webhook")).toBe(true);
      expect(await deliverOne(pool, fetchFn, "https://discord.invalid/webhook")).toBe(false);
      expect(requests.length).toBe(2);
    } finally {
      await ctx.cleanup();
    }
  });

  for (const [source, label] of [
    ["business_france", "Business France"],
    ["wttj", "Welcome to the Jungle"],
    ["workday", "Workday"],
  ] as Array<[OfferSource, string]>) {
    test(`card footer names the source (${source})`, () => {
      const embed = discordPayload(makeEvent("ABC", { source })).embeds[0]!;
      expect(embed.footer).toEqual({ text: label });
    });
  }

  test("card with footer fits Discord 6000-char text limit", () => {
    const base = makeEvent();
    const offer = {
      ...base.offer,
      fields: Array.from({ length: 10 }, () => ({
        name: "Notes",
        value: "x".repeat(1024),
        inline: true,
      })),
    };
    const embed = discordPayload(makeEvent("ABC", { offer })).embeds[0]!;
    const totalLength =
      embed.title.length +
      embed.footer.text.length +
      embed.fields.reduce((acc, f) => acc + f.name.length + f.value.length, 0);
    expect(totalLength).toBeLessThanOrEqual(6000);
  });

  for (const [deliveries, delay] of [
    [1, 30],
    [2, 60],
    [5, 480],
    [8, 3600],
    [50, 3600],
  ] as const) {
    test(`failed messages back off up to an hour (delivery ${deliveries})`, () => {
      expect(retryDelay(deliveries)).toBe(delay);
    });
  }

  test("failed message is retained with backoff", async () => {
    const delays: Array<number | undefined> = [];
    const message = {
      subject: "offers.wttj.v1",
      data: Buffer.from('{"version": 1}', "utf8"),
      info: { deliveryCount: 3, streamSequence: 42 },
      async ackAck() {
        return true;
      },
      nak(millis?: number) {
        delays.push(millis);
      },
    };

    expect(await handle({} as DbPool, message)).toBe(false);
    expect(delays).toEqual([120_000]);
  });

  test.skipIf(!getMysqlAdminUrl())("delivery waits for Discord to save the message", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("discord");
      await accept(pool, makeEvent());
      const urls: string[] = [];

      const ok = await deliverOne(
        pool,
        async (url) => {
          urls.push(url);
          return jsonResponse({ id: "1" }, 200);
        },
        "https://discord.invalid/webhook",
      );
      expect(ok).toBe(true);
      expect(new URL(urls[0]!).searchParams.get("wait")).toBe("true");
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("lost lease after sending is logged", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("discord");
      await accept(pool, makeEvent());
      const messages: string[] = [];
      const sinkId = logger.addSink((msg) => messages.push(msg), "WARNING");
      try {
        expect(
          await deliverOne(
            pool,
            async () => new Response(null, { status: 200 }),
            "https://discord.invalid/webhook",
            { finishFn: async () => false },
          ),
        ).toBe(true);
      } finally {
        logger.removeSink(sinkId);
      }
      expect(messages.some((msg) => msg.includes("lease"))).toBe(true);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("rate limited delivery waits for Discord", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("discord");
      const discovered = makeEvent();
      await accept(pool, discovered);
      const waits: number[] = [];
      const messages: string[] = [];
      const sinkId = logger.addSink((msg) => messages.push(msg), "WARNING");

      try {
        expect(
          await deliverOne(
            pool,
            async () => new Response(null, { status: 429, headers: { "Retry-After": "7" } }),
            "https://discord.invalid/webhook",
            {
              sleep: async (s) => {
                waits.push(s);
              },
            },
          ),
        ).toBe(true);
      } finally {
        logger.removeSink(sinkId);
      }

      expect(waits).toEqual([7]);
      expect(messages.some((msg) => msg.includes("429"))).toBe(true);

      const [[row]] = await pool.execute<RowDataPacket[]>(
        "SELECT completed_at, available_at FROM deliveries WHERE event_id = ?",
        [discovered.event_id],
      );
      expect(row?.completed_at).toBeNull();
      expect(parseUtcDateTime(String(row?.available_at)).getTime()).toBeGreaterThanOrEqual(
        Date.now() + 5000,
      );
    } finally {
      await ctx.cleanup();
    }
  });

  for (const status of [400, 302]) {
    test.skipIf(!getMysqlAdminUrl())(
      `rejected delivery logs status without the webhook (${status})`,
      async () => {
        const ctx = await createTestDbContext();
        try {
          const pool = await ctx.create("discord");
          await accept(pool, makeEvent());
          const messages: string[] = [];
          const sinkId = logger.addSink((msg) => messages.push(msg), "WARNING");
          try {
            await expect(
              deliverOne(
                pool,
                async () => new Response(null, { status }),
                "https://discord.invalid/webhook",
              ),
            ).rejects.toBeInstanceOf(HttpStatusError);
          } finally {
            logger.removeSink(sinkId);
          }
          expect(messages.some((msg) => msg.includes(`HTTP ${status}`))).toBe(true);
          expect(messages.some((msg) => msg.includes("discord.invalid"))).toBe(false);
        } finally {
          await ctx.cleanup();
        }
      },
    );
  }
});
