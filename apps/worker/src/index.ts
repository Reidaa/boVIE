import { randomUUID } from "node:crypto";

import "dotenv/config";
import { eq, sql } from "drizzle-orm";
import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import {
  RetentionPolicy,
  StorageType,
  connect,
  consumerOpts,
  createInbox,
  type JsMsg,
  StringCodec,
} from "nats";
import pg from "pg";

import { bovieJob } from "./schema.js";
import type { JobDiscoveredEvent } from "./types.js";

const { Pool } = pg;

const natsUrl = process.env.NATS_URL ?? "nats://localhost:4222";
const natsStream = process.env.NATS_STREAM ?? "BOVIE_JOBS";
const natsSubject = process.env.NATS_JOB_SUBJECT ?? "jobs.discovered";
const natsConsumer = process.env.NATS_CONSUMER ?? "bovie-worker";
const discordWebhookUrl = process.env.DISCORD_WEBHOOK_URL ?? "";
const databaseUrl = requiredEnv("DATABASE_URL");
const codec = StringCodec();

async function main(): Promise<void> {
  const pool = new Pool({ connectionString: databaseUrl });
  const db = drizzle(pool);
  await ensureSchema(db);

  const nc = await connect({ servers: natsUrl });
  const jsm = await nc.jetstreamManager();
  await ensureStream(jsm);

  const js = nc.jetstream();
  const opts = consumerOpts();
  opts.durable(natsConsumer);
  opts.manualAck();
  opts.ackExplicit();
  opts.deliverTo(createInbox());
  opts.deliverAll();
  opts.ackWait(60_000);

  const sub = await js.subscribe(natsSubject, opts);
  console.log(`Listening on ${natsUrl} subject=${natsSubject} consumer=${natsConsumer}`);

  const shutdown = async () => {
    console.log("Shutting down worker");
    await sub.drain();
    await nc.drain();
    await pool.end();
  };

  process.once("SIGINT", () => void shutdown());
  process.once("SIGTERM", () => void shutdown());

  for await (const msg of sub) {
    await handleMessage(db, msg);
  }
}

async function ensureStream(jsm: Awaited<ReturnType<Awaited<ReturnType<typeof connect>>["jetstreamManager"]>>) {
  try {
    await jsm.streams.info(natsStream);
  } catch {
    await jsm.streams.add({
      name: natsStream,
      subjects: [natsSubject],
      retention: RetentionPolicy.Limits,
      storage: StorageType.File,
      duplicate_window: 86_400_000_000_000,
    });
  }
}

async function ensureSchema(db: NodePgDatabase): Promise<void> {
  await db.execute(sql`
    CREATE TABLE IF NOT EXISTS bovie_job (
      id uuid PRIMARY KEY,
      offer_id bigint NOT NULL UNIQUE,
      source text NOT NULL,
      payload jsonb NOT NULL,
      discovered_at timestamptz,
      processed_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now()
    )
  `);

  await db.execute(sql`ALTER TABLE bovie_job ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'unknown'`);
  await db.execute(sql`ALTER TABLE bovie_job ADD COLUMN IF NOT EXISTS payload jsonb NOT NULL DEFAULT '{}'::jsonb`);
  await db.execute(sql`ALTER TABLE bovie_job ADD COLUMN IF NOT EXISTS discovered_at timestamptz`);
  await db.execute(sql`ALTER TABLE bovie_job ADD COLUMN IF NOT EXISTS processed_at timestamptz`);
  await db.execute(sql`ALTER TABLE bovie_job ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now()`);
  await db.execute(sql`CREATE UNIQUE INDEX IF NOT EXISTS bovie_job_offer_id_idx ON bovie_job (offer_id)`);
}

async function handleMessage(db: NodePgDatabase, msg: JsMsg): Promise<void> {
  const raw = codec.decode(msg.data);
  const event = parseEvent(raw);

  try {
    const processed = await db.transaction(async (tx) => {
      await tx.execute(sql`SELECT pg_advisory_xact_lock(${event.offerId})`);

      await tx
        .insert(bovieJob)
        .values({
          id: randomUUID(),
          offerId: event.offerId,
          source: event.source,
          payload: event,
          discoveredAt: new Date(event.discoveredAt),
        })
        .onConflictDoNothing({ target: bovieJob.offerId });

      const [existing] = await tx
        .select({ processedAt: bovieJob.processedAt })
        .from(bovieJob)
        .where(eq(bovieJob.offerId, event.offerId))
        .limit(1);

      if (existing?.processedAt) {
        return false;
      }

      await postToDiscord(event);
      await tx
        .update(bovieJob)
        .set({ processedAt: new Date() })
        .where(eq(bovieJob.offerId, event.offerId));

      return true;
    });

    msg.ack();

    if (!processed) {
      console.log(`Skipped duplicate offer ${event.offerId}`);
      return;
    }

    console.log(
      `Processed offer ${event.offerId}: ${event.job.missionTitle ?? "untitled"} ` +
        `in ${event.job.countryName ?? "unknown country"}`,
    );
  } catch (error) {
    msg.nak(30_000);
    console.error("Failed to process NATS message:", error);
  }
}

async function postToDiscord(event: JobDiscoveredEvent): Promise<void> {
  if (!discordWebhookUrl) {
    return;
  }

  const response = await fetch(discordWebhookUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      username: "boVIE",
      content: [
        `New VIE/VIA offer: ${event.job.missionTitle ?? `#${event.offerId}`}`,
        event.job.organizationName,
        event.job.countryName,
      ]
        .filter(Boolean)
        .join(" - "),
    }),
  });

  if (!response.ok) {
    throw new Error(`Discord webhook failed with HTTP ${response.status}`);
  }
}

function parseEvent(raw: string): JobDiscoveredEvent {
  const parsed = JSON.parse(raw) as Partial<JobDiscoveredEvent>;

  if (!Number.isInteger(parsed.offerId)) {
    throw new Error("Invalid job event: offerId must be an integer");
  }

  if (!parsed.job || parsed.job.id !== parsed.offerId) {
    throw new Error("Invalid job event: job.id must match offerId");
  }

  return {
    schemaVersion: parsed.schemaVersion ?? 1,
    source: parsed.source ?? "business-france-civiweb",
    discoveredAt: parsed.discoveredAt ?? new Date().toISOString(),
    offerId: parsed.offerId,
    job: parsed.job,
  };
}

function requiredEnv(name: string): string {
  const value = process.env[name];

  if (!value) {
    throw new Error(`${name} is required`);
  }

  return value;
}

void main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
