import { describe, expect, test } from "bun:test";
import { createSearchParameters, task } from "@bovie/collector-business-france";
import { collect } from "@bovie/collector-wttj";
import { CONSUMER_CONFIG, ensureConsumer, receiveMessage } from "@bovie/discord-intake";
import { deliverOne } from "@bovie/discord-sender";
import { accept } from "@bovie/discord-store";
import type { RowDataPacket } from "@bovie/mysql-common";
import {
  CONSUMER,
  ensureStream,
  isNotFoundError,
  Publisher,
  STREAM,
  STREAM_CONFIG,
} from "@bovie/nats-client";
import { type OfferEvent, parseOfferEventJson } from "@bovie/offer-events";
import { jetstream, jetstreamManager } from "@nats-io/jetstream";
import { nanos } from "@nats-io/nats-core";
import { connect as natsConnect } from "@nats-io/transport-node";
import { makeBfJob } from "./collection.test.js";
import {
  createTestDbContext,
  getMysqlAdminUrl,
  getNatsTestUrl,
  jsonResponse,
} from "./helpers/db.js";
import { makeWttjDetail, makeWttjHit } from "./wttj.test.js";

async function deleteStream(url: string): Promise<void> {
  const nc = await natsConnect({ servers: [url] });
  try {
    const jsm = await jetstreamManager(nc);
    try {
      await jsm.streams.delete(STREAM);
    } catch (error) {
      if (!isNotFoundError(error)) {
        throw error;
      }
    }
  } finally {
    await nc.close();
  }
}

describe("NATS JetStream integration", () => {
  test.skipIf(!getNatsTestUrl() || !getMysqlAdminUrl())(
    "both sources through real JetStream and captured Discord",
    async () => {
      const url = getNatsTestUrl()!;
      const prevUrl = process.env.NATS_URL;
      const prevUser = process.env.NATS_USER;
      const prevPass = process.env.NATS_PASSWORD;
      process.env.NATS_URL = url;
      delete process.env.NATS_USER;
      delete process.env.NATS_PASSWORD;

      const ctx = await createTestDbContext();
      try {
        await deleteStream(url);
        const businessFranceDb = await ctx.create("collector");
        const wttjDb = await ctx.create("collector");
        const discordDb = await ctx.create("discord");

        const published: OfferEvent[] = [];
        const publisher = new Publisher();
        await publisher.connect();
        try {
          const publish = async (event: OfferEvent) => {
            await publisher.publish(event);
            published.push(event);
          };

          await task(createSearchParameters({ limit: 1 }), businessFranceDb, publish, {
            deps: {
              searchId: async () => [1],
              getFromId: async (id) => makeBfJob(id),
            },
          });

          const wttjFetch = async (input: string) => {
            if (new URL(input).pathname.endsWith("/public/jobs")) {
              return jsonResponse({
                data: [makeWttjHit("wttj-1")],
                metadata: { page: 1, page_count: 1 },
              });
            }
            return jsonResponse(makeWttjDetail("wttj-1"));
          };
          await collect(wttjDb, wttjFetch, publish, { baseUrl: "https://source.invalid" });

          // A run that crashed before recording republishes the same event ID.
          await publisher.publish(published[0]!);
        } finally {
          await publisher.close();
        }

        const nc = await natsConnect({ servers: [url] });
        try {
          const jsm = await jetstreamManager(nc);
          await ensureConsumer(jsm);
          // A short ack wait exercises broker redelivery after a lost consumer ack.
          await jsm.consumers.update(STREAM, CONSUMER, {
            ...CONSUMER_CONFIG,
            ack_wait: nanos(1500),
          });
          const js = jetstream(nc);
          const consumer = await js.consumers.get(STREAM, CONSUMER);

          const batch = await consumer.fetch({ max_messages: 3, expires: 1000 });
          const messages = [];
          for await (const msg of batch) {
            messages.push(msg);
          }
          expect(messages.length).toBe(2);

          // Commit the first message but lose its acknowledgment.
          await accept(discordDb, parseOfferEventJson(messages[0]!.data));
          await receiveMessage(discordDb, messages[1]!);

          const replayBatch = await consumer.fetch({ max_messages: 1, expires: 3000 });
          const replayed = [];
          for await (const msg of replayBatch) {
            replayed.push(msg);
          }
          expect(replayed.length).toBe(1);
          expect(Buffer.from(replayed[0]!.data)).toEqual(Buffer.from(messages[0]!.data));
          await receiveMessage(discordDb, replayed[0]!);

          // Acknowledged messages stay in the stream for other consumers.
          const info = await jsm.streams.info(STREAM);
          expect(info.state.messages).toBe(2);
        } finally {
          await nc.close();
        }

        const [[deliveryCount]] = await discordDb.query<RowDataPacket[]>(
          "SELECT COUNT(*) AS count FROM deliveries",
        );
        expect(Number(deliveryCount?.count)).toBe(2);

        const sent: string[] = [];
        while (
          await deliverOne(
            discordDb,
            async (reqUrl) => {
              sent.push(reqUrl);
              return new Response(null, { status: 204 });
            },
            "https://discord.invalid/webhook",
          )
        ) {
          // drain
        }
        expect(sent.length).toBe(2);
      } finally {
        await deleteStream(url);
        await ctx.cleanup();
        if (prevUrl === undefined) delete process.env.NATS_URL;
        else process.env.NATS_URL = prevUrl;
        if (prevUser === undefined) delete process.env.NATS_USER;
        else process.env.NATS_USER = prevUser;
        if (prevPass === undefined) delete process.env.NATS_PASSWORD;
        else process.env.NATS_PASSWORD = prevPass;
      }
    },
  );

  test.skipIf(!getNatsTestUrl())("existing stream keeps operator limits", async () => {
    const url = getNatsTestUrl()!;
    await deleteStream(url);
    const nc = await natsConnect({ servers: [url] });
    try {
      const jsm = await jetstreamManager(nc);
      await jsm.streams.add({ ...STREAM_CONFIG, max_bytes: 1024 });
      await ensureStream(jsm);
      const info = await jsm.streams.info(STREAM);
      expect(info.config.max_bytes).toBe(1024);
    } finally {
      await nc.close();
      await deleteStream(url);
    }
  });

  test.skipIf(!getNatsTestUrl())(
    "intake waits for the first collector to create the stream",
    async () => {
      const url = getNatsTestUrl()!;
      await deleteStream(url);
      const nc = await natsConnect({ servers: [url] });
      try {
        const jsm = await jetstreamManager(nc);
        // `--once` has nothing to drain before the stream exists.
        expect(await ensureConsumer(jsm, { wait: false, streamWaitSeconds: 0.1 })).toBe(false);

        let settled = false;
        const waiting = ensureConsumer(jsm, { wait: true, streamWaitSeconds: 0.1 }).then((ok) => {
          settled = true;
          return ok;
        });

        await new Promise((resolve) => setTimeout(resolve, 300));
        expect(settled).toBe(false);

        await ensureStream(jsm);
        expect(await waiting).toBe(true);

        const info = await jsm.consumers.info(STREAM, CONSUMER);
        expect(info.config.ack_wait).toBe(nanos(120 * 1000));
      } finally {
        await nc.close();
        await deleteStream(url);
      }
    },
  );

  test.skipIf(!getNatsTestUrl())(
    "connect retries until a late server starts",
    async () => {
      const { connect } = await import("@bovie/nats-client");
      const target = new URL(getNatsTestUrl()!);
      // Reserve a free port, then free it so the first dials are refused.
      const probe = Bun.listen({ hostname: "127.0.0.1", port: 0, socket: { data() {} } });
      const port = probe.port;
      probe.stop(true);

      const connecting = connect({ url: `nats://127.0.0.1:${port}` });
      await Bun.sleep(2500);
      // Start a TCP proxy to the real server on the reserved port.
      const proxy = Bun.listen<{ upstream?: Awaited<ReturnType<typeof Bun.connect>> }>({
        hostname: "127.0.0.1",
        port,
        socket: {
          async open(client) {
            client.data = {};
            client.data.upstream = await Bun.connect({
              hostname: target.hostname,
              port: Number(target.port),
              socket: {
                data(_, chunk) {
                  client.write(chunk);
                },
                close() {
                  client.end();
                },
              },
            });
          },
          data(client, chunk) {
            client.data.upstream?.write(chunk);
          },
          close(client) {
            client.data.upstream?.end();
          },
        },
      });
      try {
        const nc = await connecting;
        expect(nc.isClosed()).toBe(false);
        await nc.close();
      } finally {
        proxy.stop(true);
      }
    },
    15_000,
  );
});
