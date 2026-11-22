import { createHash } from "node:crypto";
import {
  type DbPool,
  formatUtcDateTime,
  parseUtcDateTime,
  type RowDataPacket,
  utcNowString,
} from "@bovie/mysql-common";
import { upgradeSchema, type WaitDeps } from "@bovie/mysql-common/migrate";
import { contentHash, type OfferEvent, serializeOfferEvent } from "@bovie/offer-events";
import { COLLECTOR_MIGRATIONS } from "./migrations.js";

export { COLLECTOR_MIGRATIONS } from "./migrations.js";

// Collectors run every 2 hours, so this is 6 runs in a row without results.
export const MAX_SILENCE_MS = 12 * 60 * 60 * 1000;

export class SourceSilent extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SourceSilent";
  }
}

// Python's json.dumps defaults: ", " and ": " separators, DEL and non-ASCII escaped as \uXXXX.
function pythonJsonDumps(value: unknown, sortKeys: boolean): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => pythonJsonDumps(item, sortKeys)).join(", ")}]`;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (sortKeys) {
      entries.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
    }
    return `{${entries.map(([k, v]) => `${pythonJsonDumps(k, sortKeys)}: ${pythonJsonDumps(v, sortKeys)}`).join(", ")}}`;
  }
  return JSON.stringify(value).replace(
    /[\u007f-\uffff]/g,
    (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`,
  );
}

/**
 * Hash a collector's search parameters into its checkpoint `scan` key.
 *
 * Collectors call this once per run. The output matches the Python collectors'
 * sha256(json.dumps(params[, sort_keys=True])), so existing checkpoints stay valid.
 */
export function scanHash(params: unknown, options: { sortKeys?: boolean } = {}): string {
  return createHash("sha256")
    .update(pythonJsonDumps(params, options.sortKeys ?? false), "utf8")
    .digest("hex");
}

export async function upgrade(
  pool: DbPool,
  options: { waitTimeout?: number; deps?: WaitDeps } = {},
): Promise<void> {
  await upgradeSchema(pool, COLLECTOR_MIGRATIONS, options);
}

export async function seen(pool: DbPool, sourceOfferId: string): Promise<boolean> {
  const [rows] = await pool.execute<RowDataPacket[]>(
    "SELECT 1 FROM offers WHERE source_offer_id = ? LIMIT 1",
    [sourceOfferId],
  );
  return rows.length > 0;
}

/**
 * Record published offers, refresh last_seen_at for the page, and checkpoint.
 *
 * Call only after the broker acknowledged every event in `published`.
 */
export async function recordPage(
  pool: DbPool,
  published: Iterable<OfferEvent>,
  observed: Iterable<string>,
  scan: string,
  offset: number,
): Promise<void> {
  const now = utcNowString();
  await pool.withTransaction(async (conn) => {
    for (const event of published) {
      // A concurrent run may have recorded the same offer first; keep its row.
      await conn.execute(
        `INSERT INTO offers (source_offer_id, observed_at, event_id, payload, content_hash, last_seen_at)
         VALUES (?, ?, ?, ?, ?, ?)
         ON DUPLICATE KEY UPDATE source_offer_id = source_offer_id`,
        [
          event.source_offer_id,
          formatUtcDateTime(event.observed_at),
          event.event_id,
          serializeOfferEvent(event),
          contentHash(event.offer),
          now,
        ],
      );
    }

    const identities = Array.from(observed);
    if (identities.length > 0) {
      const placeholders = identities.map(() => "?").join(", ");
      await conn.execute(
        `UPDATE offers SET last_seen_at = ? WHERE source_offer_id IN (${placeholders})`,
        [now, ...identities],
      );
    }

    if (identities.length > 0) {
      await conn.execute(
        `INSERT INTO checkpoints (scan, \`offset\`, results_seen_at)
         VALUES (?, ?, ?)
         ON DUPLICATE KEY UPDATE \`offset\` = VALUES(\`offset\`), results_seen_at = VALUES(results_seen_at)`,
        [scan, offset, now],
      );
    } else {
      await conn.execute(
        `INSERT INTO checkpoints (scan, \`offset\`, results_seen_at)
         VALUES (?, ?, NULL)
         ON DUPLICATE KEY UPDATE \`offset\` = VALUES(\`offset\`)`,
        [scan, offset],
      );
    }
  });
}

/**
 * Throw SourceSilent unless the scan returned results within MAX_SILENCE_MS.
 *
 * Call at the end of each run, after the last `recordPage`.
 */
export async function requireRecentResults(pool: DbPool, scan: string): Promise<void> {
  const [rows] = await pool.execute<RowDataPacket[]>(
    "SELECT results_seen_at FROM checkpoints WHERE scan = ?",
    [scan],
  );
  const raw = rows[0]?.results_seen_at;
  if (raw === null || raw === undefined) {
    throw new SourceSilent("The source has not returned any results yet");
  }
  const seenAt = parseUtcDateTime(String(raw));
  if (Date.now() - seenAt.getTime() > MAX_SILENCE_MS) {
    throw new SourceSilent(`The source has returned no results since ${seenAt.toISOString()}`);
  }
}
