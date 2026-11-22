import { logger } from "@bovie/cli-common";
import { DELIVERIES_TABLE } from "@bovie/discord-store";
import type { DbPool } from "@bovie/mysql-common";
import { claim, finish, retryLater } from "@bovie/mysql-common/queue";
import { type OfferEvent, type OfferSource, parseOfferEvent } from "@bovie/offer-events";

// The card footer names the source, so readers can tell where an offer came from.
export const SOURCE_LABELS: Record<OfferSource, string> = {
  business_france: "Business France",
  wttj: "Welcome to the Jungle",
  workday: "Workday",
};

export class HttpStatusError extends Error {
  readonly status: number;

  constructor(status: number) {
    // Never include the webhook URL in the error message.
    super(`Discord answered HTTP ${status}`);
    this.name = "HttpStatusError";
    this.status = status;
  }
}

export interface DiscordEmbedField {
  name: string;
  value: string;
  inline?: boolean;
}

export interface DiscordWebhookPayload {
  username: string;
  allowed_mentions: { parse: string[] };
  embeds: Array<{
    title: string;
    url: string;
    color: number;
    fields: DiscordEmbedField[];
    footer: { text: string };
  }>;
}

export function discordPayload(event: OfferEvent): DiscordWebhookPayload {
  const offer = event.offer;
  let fields: DiscordEmbedField[] = offer.fields.map((field) => ({
    name: field.name,
    value: field.value,
    inline: field.inline,
  }));
  if (fields.length === 0) {
    fields = [
      { name: "Entreprise", value: offer.organization.slice(0, 1024) || "N/A" },
      { name: "Lieu", value: `${offer.city}, ${offer.country}`.slice(0, 1024) },
    ];
  }
  const footer = SOURCE_LABELS[event.source];
  // Discord's aggregate embed text limit is 6000 characters.
  let remaining = 6000 - offer.title.length - footer.length;
  const bounded: DiscordEmbedField[] = [];
  for (const field of fields) {
    const available = remaining - field.name.length;
    if (available <= 0) {
      break;
    }
    const truncatedValue = field.value.slice(0, available);
    remaining -= field.name.length + truncatedValue.length;
    bounded.push({ ...field, value: truncatedValue });
  }
  return {
    username: "boVIE",
    allowed_mentions: { parse: [] },
    embeds: [
      {
        title: offer.title,
        url: offer.url,
        color: 341401,
        fields: bounded,
        footer: { text: footer },
      },
    ],
  };
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

const defaultSleep = (seconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, seconds * 1000));

export interface DeliverOptions {
  timeoutMs?: number;
  sleep?: (seconds: number) => Promise<void>;
  finishFn?: typeof finish;
}

export async function deliverOne(
  pool: DbPool,
  fetchFn: FetchLike,
  webhook: string,
  options: DeliverOptions = {},
): Promise<boolean> {
  const timeoutMs = options.timeoutMs ?? 15_000;
  const sleep = options.sleep ?? defaultSleep;
  const finishWork = options.finishFn ?? finish;

  const work = await claim(pool, DELIVERIES_TABLE);
  if (work === null) {
    return false;
  }

  let response: Response;
  try {
    // wait=true makes Discord confirm the message was saved before it answers.
    const url = new URL(webhook);
    url.searchParams.set("wait", "true");
    response = await fetchFn(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(discordPayload(parseOfferEvent(work.payload))),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    await retryLater(pool, DELIVERIES_TABLE, work);
    throw error;
  }

  if (response.status === 429) {
    // Wait as long as Discord asks; sending sooner only extends the limit.
    const retryAfterHeader = response.headers.get("Retry-After");
    const parsedWait = retryAfterHeader !== null ? Number(retryAfterHeader) : 1;
    const wait = Number.isFinite(parsedWait) && parsedWait >= 0 ? parsedWait : 1;
    await retryLater(pool, DELIVERIES_TABLE, work, { delaySeconds: wait });
    logger.warning(`Discord answered HTTP 429; waiting ${wait} s`);
    await sleep(wait);
    return true;
  }

  if (response.status < 200 || response.status >= 300) {
    // Log only the status: never expose the webhook URL.
    logger.warning(`Discord answered HTTP ${response.status}`);
    await retryLater(pool, DELIVERIES_TABLE, work);
    throw new HttpStatusError(response.status);
  }

  if (!(await finishWork(pool, DELIVERIES_TABLE, work))) {
    logger.warning(
      `Delivery ${work.eventId} was sent after its lease expired; Discord may show it twice`,
    );
  }
  return true;
}
