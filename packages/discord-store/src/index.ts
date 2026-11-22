import { type DbPool, type RowDataPacket, utcNowString } from "@bovie/mysql-common";
import { upgradeSchema, type WaitDeps } from "@bovie/mysql-common/migrate";
import { type OfferEvent, serializeOfferEvent } from "@bovie/offer-events";
import { DISCORD_MIGRATIONS } from "./migrations.js";

export { DISCORD_MIGRATIONS } from "./migrations.js";

export const DELIVERIES_TABLE = "deliveries";

export async function upgrade(
  pool: DbPool,
  options: { waitTimeout?: number; deps?: WaitDeps } = {},
): Promise<void> {
  await upgradeSchema(pool, DISCORD_MIGRATIONS, options);
}

function identity(payload: Record<string, unknown>): string {
  return JSON.stringify([payload.source, payload.source_offer_id, payload.type]);
}

function parseJsonColumn(value: unknown): Record<string, unknown> {
  if (typeof value === "string") {
    return JSON.parse(value) as Record<string, unknown>;
  }
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  throw new Error("Unexpected JSON payload column");
}

/**
 * Store the event once and queue a Discord delivery for new discoveries.
 *
 * A republished event keeps its ID but can carry a later observed_at, so
 * duplicates are matched on the offer identity, not on the whole payload.
 */
export async function accept(pool: DbPool, event: OfferEvent): Promise<boolean> {
  const serialized = serializeOfferEvent(event);
  const payload = JSON.parse(serialized) as Record<string, unknown>;
  const eventId = event.event_id;
  const now = utcNowString();

  return await pool.withTransaction(async (conn) => {
    await conn.execute(
      `INSERT INTO inbox (event_id, payload, received_at)
       VALUES (?, ?, ?)
       ON DUPLICATE KEY UPDATE event_id = VALUES(event_id)`,
      [eventId, serialized, now],
    );

    const [inboxRows] = await conn.execute<RowDataPacket[]>(
      "SELECT payload FROM inbox WHERE event_id = ?",
      [eventId],
    );
    const saved = inboxRows[0];
    if (!saved || identity(parseJsonColumn(saved.payload)) !== identity(payload)) {
      throw new Error("Event ID already belongs to a different offer");
    }

    if (event.type !== "discovered") {
      return false;
    }

    const [deliveryRows] = await conn.execute<RowDataPacket[]>(
      "SELECT 1 FROM deliveries WHERE event_id = ? LIMIT 1",
      [eventId],
    );
    if (deliveryRows.length > 0) {
      return false;
    }

    await conn.execute(
      `INSERT INTO deliveries (event_id, payload, attempts, available_at)
       VALUES (?, ?, 0, ?)`,
      [eventId, serialized, now],
    );
    return true;
  });
}
