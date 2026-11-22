import { describe, expect, test } from "bun:test";
import { ensureConsumer } from "@bovie/discord-intake";
import { CONSUMER, connect, ensureStream, isNotFoundError, STREAM } from "@bovie/nats-client";
import { type OfferSource, serializeOfferEvent } from "@bovie/offer-events";
import { jetstream, jetstreamManager } from "@nats-io/jetstream";
import type { NatsConnection } from "@nats-io/nats-core";
import { connect as natsConnect } from "@nats-io/transport-node";
import { getNatsAuthTestUrl, makeEvent } from "./helpers/db.js";

const PASSWORDS: Record<string, string> = {
  "nats-setup": "local-nats-setup",
  "collector-business-france": "local-nats-collector-business-france",
  "collector-wttj": "local-nats-collector-wttj",
  "collector-workday": "local-nats-collector-workday",
  "discord-intake": "local-nats-discord-intake",
};

async function cleanupStream(url: string): Promise<void> {
  const admin = await connect({
    url,
    user: "nats-setup",
    password: PASSWORDS["nats-setup"],
  });
  try {
    const jsm = await jetstreamManager(admin, { checkAPI: false });
    try {
      await jsm.streams.delete(STREAM);
    } catch (error) {
      if (!isNotFoundError(error)) {
        throw error;
      }
    }
  } finally {
    await admin.close();
  }
}

describe("NATS deployment permissions", () => {
  test.skipIf(!getNatsAuthTestUrl())(
    "deployment NATS permissions and durable acknowledgments",
    async () => {
      const url = getNatsAuthTestUrl()!;
      const connections: NatsConnection[] = [];

      const connectAs = async (user: string): Promise<NatsConnection> => {
        const nc = await connect({ url, user, password: PASSWORDS[user] });
        connections.push(nc);
        return nc;
      };

      try {
        // On an empty broker, the collectors create the stream themselves.
        for (const [source, user] of [
          ["business_france", "collector-business-france"],
          ["wttj", "collector-wttj"],
          ["workday", "collector-workday"],
        ] as Array<[OfferSource, string]>) {
          const nc = await connectAs(user);
          const jsm = await jetstreamManager(nc, { checkAPI: false });
          await ensureStream(jsm);
          const discovered = makeEvent("ABC", { source });
          await jetstream(nc).publish(
            `offers.${source}.v1`,
            Buffer.from(serializeOfferEvent(discovered), "utf8"),
          );
        }

        const receiver = await connectAs("discord-intake");
        const receiverJsm = await jetstreamManager(receiver, { checkAPI: false });
        expect(await ensureConsumer(receiverJsm)).toBe(true);
        const consumer = await jetstream(receiver).consumers.get(STREAM, CONSUMER);
        const batch = await consumer.fetch({ max_messages: 3, expires: 2000 });
        let acked = 0;
        for await (const message of batch) {
          await message.ackAck();
          acked += 1;
        }
        expect(acked).toBe(3);

        // Each account can create only its own object, and change nothing.
        const denied: Record<string, string[]> = {
          "collector-business-france": [
            "offers.wttj.v1",
            "_INBOX.discord-intake.>",
            "$JS.API.STREAM.UPDATE.OFFERS",
            "$JS.API.STREAM.DELETE.OFFERS",
            "$JS.API.STREAM.CREATE.OTHER",
          ],
          "discord-intake": [
            "$JS.API.CONSUMER.CREATE.OFFERS.other",
            "$JS.API.CONSUMER.DELETE.OFFERS.discord-intake",
          ],
        };

        for (const [user, subjects] of Object.entries(denied)) {
          const violations: string[] = [];
          const nc = await natsConnect({
            servers: [url],
            user,
            pass: PASSWORDS[user],
          });
          connections.push(nc);

          const statusDone = (async () => {
            for await (const status of nc.status()) {
              if (status.type === "error") {
                violations.push(String(status.error).toLowerCase());
                if (violations.length >= subjects.length) {
                  break;
                }
              }
            }
          })();

          for (const deniedSubject of subjects) {
            if (deniedSubject.startsWith("_INBOX.")) {
              nc.subscribe(deniedSubject);
            } else {
              nc.publish(deniedSubject, Buffer.from("not permitted", "utf8"));
            }
          }
          await nc.flush();

          await Promise.race([
            statusDone,
            new Promise((_, reject) =>
              setTimeout(
                () => reject(new Error(`Timed out waiting for permission errors for ${user}`)),
                2000,
              ),
            ),
          ]);

          for (const deniedSubject of subjects) {
            expect(violations.some((err) => err.includes(`"${deniedSubject.toLowerCase()}"`))).toBe(
              true,
            );
          }
        }
      } finally {
        for (const nc of connections) {
          await nc.close();
        }
        await cleanupStream(url);
      }
    },
  );
});
