import { type OfferEvent, serializeOfferEvent } from "@bovie/offer-events";
import {
  DiscardPolicy,
  JetStreamApiError,
  type JetStreamClient,
  type JetStreamManager,
  jetstream,
  jetstreamManager,
  RetentionPolicy,
  StorageType,
  type StreamConfig,
} from "@nats-io/jetstream";
import { headers, type NatsConnection, nanos } from "@nats-io/nats-core";
import { connect as natsConnect } from "@nats-io/transport-node";

export const STREAM = "OFFERS";
export const CONSUMER = "discord-intake";

// Limits retention keeps acknowledged messages, so several consumers can read the
// stream and a new consumer can replay the retained history.
export const STREAM_CONFIG: Partial<StreamConfig> & { name: string } = {
  name: STREAM,
  subjects: ["offers.*.v1"],
  storage: StorageType.File,
  retention: RetentionPolicy.Limits,
  max_age: nanos(90 * 24 * 60 * 60 * 1000),
  discard: DiscardPolicy.New,
  max_bytes: 1024 * 1024 * 1024,
  max_msg_size: 131072,
  duplicate_window: nanos(120 * 1000),
  num_replicas: 1,
};

export function subject(source: string): string {
  return `offers.${source}.v1`;
}

export async function connect(options?: {
  url?: string;
  user?: string;
  password?: string;
  waitOnFirstConnect?: boolean;
}): Promise<NatsConnection> {
  const user = options?.user ?? process.env.NATS_USER;
  const password = options?.password ?? process.env.NATS_PASSWORD;
  const url = options?.url ?? process.env.NATS_URL ?? "nats://127.0.0.1:4222";
  const waitOnFirstConnect = options?.waitOnFirstConnect ?? false;
  return await natsConnect({
    servers: [url],
    user: user || undefined,
    pass: password || undefined,
    inboxPrefix: user ? `_INBOX.${user}` : "_INBOX",
    timeout: 5000,
    waitOnFirstConnect,
    ...(waitOnFirstConnect ? { maxReconnectAttempts: -1, reconnectTimeWait: 2000 } : {}),
  });
}

export function isNotFoundError(error: unknown): boolean {
  if (error instanceof JetStreamApiError) {
    const api = error.apiError();
    return (
      error.code === 404 || api.code === 404 || api.err_code === 10059 || api.err_code === 10014
    );
  }
  return false;
}

/**
 * Create the offer stream when it is missing. Never change an existing one.
 *
 * Collectors call this before they publish. Their accounts can create the
 * stream but not update it, so an operator changes its limits with the
 * nats-setup account.
 */
export async function ensureStream(jsm: JetStreamManager): Promise<void> {
  try {
    await jsm.streams.info(STREAM);
  } catch (error) {
    if (!isNotFoundError(error)) {
      throw error;
    }
    // When both collectors create it at once, both calls succeed:
    // JetStream accepts a create with the same configuration.
    await jsm.streams.add(STREAM_CONFIG);
  }
}

export class Publisher {
  private readonly timeoutMs: number;
  private nc: NatsConnection | null = null;
  private js: JetStreamClient | null = null;

  constructor(timeoutSeconds = 10) {
    this.timeoutMs = timeoutSeconds * 1000;
  }

  async connect(): Promise<this> {
    const nc = await connect();
    this.nc = nc;
    try {
      const jsm = await jetstreamManager(nc, { checkAPI: false });
      await ensureStream(jsm);
      this.js = jetstream(nc);
      return this;
    } catch (error) {
      await this.close();
      throw error;
    }
  }

  async publish(event: OfferEvent): Promise<void> {
    if (!this.js) {
      throw new Error("Publisher is not connected");
    }
    const hdrs = headers();
    hdrs.set("Nats-Msg-Id", event.event_id);
    await this.js.publish(subject(event.source), Buffer.from(serializeOfferEvent(event), "utf8"), {
      headers: hdrs,
      msgID: event.event_id,
      timeout: this.timeoutMs,
    });
  }

  async close(): Promise<void> {
    const nc = this.nc;
    this.nc = null;
    this.js = null;
    if (nc) {
      await nc.close();
    }
  }

  async [Symbol.asyncDispose](): Promise<void> {
    await this.close();
  }
}
