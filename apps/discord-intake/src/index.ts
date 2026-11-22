import { logFailure, logger } from "@bovie/cli-common";
import { accept } from "@bovie/discord-store";
import type { DbPool } from "@bovie/mysql-common";
import { CONSUMER, isNotFoundError, STREAM, subject } from "@bovie/nats-client";
import { parseOfferEventJson } from "@bovie/offer-events";
import {
  AckPolicy,
  type ConsumerConfig,
  type JetStreamManager,
  type JsMsg,
} from "@nats-io/jetstream";
import { nanos } from "@nats-io/nats-core";

// A failing message is retried until it succeeds. JetStream keeps it, so a fix
// deployed later still delivers it. The delay doubles from 30 s up to this cap.
export const MAX_RETRY_DELAY = 3600;

// Setting `name` makes the client use CONSUMER.CREATE.OFFERS.discord-intake,
// the only create subject this service's account may publish to.
export const CONSUMER_CONFIG: Partial<ConsumerConfig> = {
  name: CONSUMER,
  durable_name: CONSUMER,
  ack_policy: AckPolicy.Explicit,
  ack_wait: nanos(120 * 1000),
  max_ack_pending: 1000,
};

// Seconds between checks for the stream on a broker that no collector used yet.
export const STREAM_WAIT = 30;

export interface IntakeMessage {
  readonly subject: string;
  readonly data: Uint8Array;
  readonly info: {
    readonly deliveryCount: number;
    readonly streamSequence: number;
  };
  ackAck(): Promise<boolean>;
  nak(millis?: number): void;
}

const defaultSleep = (seconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, seconds * 1000));

/**
 * Create this service's consumer when it is missing. Never change it.
 *
 * The collectors create the stream. On a new broker, intake can start first,
 * so it waits for the stream. Return false when the stream is missing and
 * `wait` is false.
 */
export async function ensureConsumer(
  jsm: JetStreamManager,
  options: {
    wait?: boolean;
    streamWaitSeconds?: number;
    sleep?: (seconds: number) => Promise<void>;
  } = {},
): Promise<boolean> {
  const wait = options.wait ?? true;
  const streamWaitSeconds = options.streamWaitSeconds ?? STREAM_WAIT;
  const sleep = options.sleep ?? defaultSleep;

  while (true) {
    try {
      await jsm.consumers.info(STREAM, CONSUMER);
      return true;
    } catch (error) {
      if (!isNotFoundError(error)) {
        throw error;
      }
    }
    try {
      await jsm.consumers.add(STREAM, CONSUMER_CONFIG);
      return true;
    } catch (error) {
      if (!isNotFoundError(error)) {
        throw error;
      }
      if (!wait) {
        return false;
      }
      logger.info(`Stream ${STREAM} does not exist yet; checking again in ${streamWaitSeconds} s`);
      await sleep(streamWaitSeconds);
    }
  }
}

export async function receiveMessage(
  pool: DbPool,
  message: Pick<IntakeMessage, "subject" | "data" | "ackAck">,
): Promise<void> {
  const event = parseOfferEventJson(message.data);
  if (message.subject !== subject(event.source)) {
    throw new Error("Event source does not match its NATS subject");
  }
  await accept(pool, event);
  await message.ackAck();
}

export function retryDelay(deliveries: number): number {
  return Math.min(30 * 2 ** (deliveries - 1), MAX_RETRY_DELAY);
}

/**
 * Process one message; on failure, log it and schedule its next delivery.
 */
export async function handle(pool: DbPool, message: IntakeMessage | JsMsg): Promise<boolean> {
  try {
    await receiveMessage(pool, message);
    return true;
  } catch (error) {
    const deliveries = message.info.deliveryCount;
    logFailure(
      error,
      `Discord intake of stream message ${message.info.streamSequence} (delivery ${deliveries})`,
    );
    message.nak(retryDelay(deliveries) * 1000);
    return false;
  }
}
