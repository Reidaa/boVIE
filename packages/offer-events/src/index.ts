import { createHash } from "node:crypto";
import { z } from "zod";

export type EventType = "discovered" | "updated" | "closed";
export type OfferSource = "business_france" | "wttj" | "workday";

// Changing this namespace changes every event ID and defeats republish deduplication.
export const EVENT_NAMESPACE = "a29ccd0b-e431-445f-8881-a6ad4aa872bf";

const AWARE_ISO_DATETIME =
  /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$/i;

function uuidToBytes(uuid: string): Uint8Array {
  const hex = uuid.replace(/-/g, "");
  if (!/^[0-9a-fA-F]{32}$/.test(hex)) {
    throw new Error(`Invalid UUID: ${uuid}`);
  }
  const bytes = new Uint8Array(16);
  for (let i = 0; i < 16; i += 1) {
    bytes[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

function bytesToUuid(bytes: Uint8Array): string {
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}

export function uuid5(namespace: string, name: string): string {
  const nsBytes = uuidToBytes(namespace);
  const nameBytes = Buffer.from(name, "utf8");
  const hash = createHash("sha1").update(nsBytes).update(nameBytes).digest();
  const bytes = new Uint8Array(hash.subarray(0, 16));
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x50;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  return bytesToUuid(bytes);
}

const HttpUrlSchema = z.string().transform((value, ctx) => {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      ctx.addIssue({
        code: "custom",
        message: "URL must use http or https scheme",
      });
      return z.NEVER;
    }
    return parsed.toString();
  } catch {
    ctx.addIssue({
      code: "custom",
      message: "Invalid URL",
    });
    return z.NEVER;
  }
});

export const DisplayFieldSchema = z.object({
  name: z.string().min(1).max(256),
  value: z.string().min(1).max(1024),
  inline: z.boolean().default(true),
});

export type DisplayField = z.infer<typeof DisplayFieldSchema>;

export const OfferDetailsSchema = z.object({
  title: z.string().min(1).max(256),
  organization: z.string(),
  country: z.string(),
  city: z.string(),
  url: HttpUrlSchema,
  fields: z.array(DisplayFieldSchema).max(25).default([]),
});

export type OfferDetails = z.infer<typeof OfferDetailsSchema>;
export type OfferDetailsInput = z.input<typeof OfferDetailsSchema>;

export function contentHash(offer: OfferDetails): string {
  const canonical = {
    title: offer.title,
    organization: offer.organization,
    country: offer.country,
    city: offer.city,
    url: offer.url,
    fields: offer.fields.map((field) => ({
      name: field.name,
      value: field.value,
      inline: field.inline,
    })),
  };
  return createHash("sha256").update(JSON.stringify(canonical), "utf8").digest("hex");
}

export function stableEventId(data: {
  source: OfferSource;
  source_offer_id: string;
  type: EventType;
  offer: OfferDetails;
}): string {
  let identity = `${data.source}:${data.source_offer_id}:${data.type}`;
  if (data.type === "updated") {
    identity += `:${contentHash(data.offer)}`;
  }
  return uuid5(EVENT_NAMESPACE, identity);
}

const AwareDatetimeSchema = z
  .string()
  .refine((value) => AWARE_ISO_DATETIME.test(value) && !Number.isNaN(Date.parse(value)), {
    message: "Timestamps must be timezone-aware ISO-8601 strings",
  });

const OfferEventRawSchema = z.strictObject({
  version: z.literal(1).default(1),
  type: z.enum(["discovered", "updated", "closed"]),
  source: z.enum(["business_france", "wttj", "workday"]),
  source_offer_id: z
    .string()
    .min(1)
    .max(255)
    .refine((value) => value === value.trim(), {
      message: "Source identity cannot have surrounding whitespace",
    }),
  offer: OfferDetailsSchema,
  event_id: z.string().uuid().optional(),
  observed_at: AwareDatetimeSchema.optional(),
});

export const OfferEventSchema = OfferEventRawSchema.transform((data) => ({
  version: data.version,
  type: data.type,
  source: data.source,
  source_offer_id: data.source_offer_id,
  offer: data.offer,
  event_id: data.event_id ?? stableEventId(data),
  observed_at: data.observed_at ?? new Date().toISOString(),
}));

export type OfferEvent = z.output<typeof OfferEventSchema>;
export type OfferEventInput = z.input<typeof OfferEventSchema>;

export function createOfferEvent(input: OfferEventInput): OfferEvent {
  return OfferEventSchema.parse(input);
}

export function parseOfferEvent(input: unknown): OfferEvent {
  return OfferEventSchema.parse(input);
}

export function parseOfferEventJson(raw: string | Uint8Array): OfferEvent {
  const text = typeof raw === "string" ? raw : Buffer.from(raw).toString("utf8");
  return OfferEventSchema.parse(JSON.parse(text));
}

export function serializeOfferEvent(event: OfferEvent): string {
  return JSON.stringify(event);
}
