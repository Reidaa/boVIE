import { logger } from "@bovie/cli-common";
import { recordPage, requireRecentResults, scanHash, seen } from "@bovie/collector-store";
import type { DbPool } from "@bovie/mysql-common";
import { createOfferEvent, type OfferEvent } from "@bovie/offer-events";
import { displayFields } from "./display.js";
import { BusinessFranceClient, type Job, type SearchParameters } from "./job.js";

export * from "./config.js";
export * from "./datasets.js";
export * from "./display.js";
export * from "./job.js";

export const DEFAULT_OFFER_LIMIT = 25;

export function normalize(job: Job): OfferEvent {
  return createOfferEvent({
    type: "discovered",
    source: "business_france",
    source_offer_id: String(job.id),
    offer: {
      title: job.missionTitle.slice(0, 256),
      organization: job.organizationName,
      country: job.countryName,
      city: job.cityName || job.cityAffectation,
      url: `https://mon-vie-via.businessfrance.fr/offres/${job.id}`,
      fields: displayFields(job),
    },
  });
}

export interface TaskDeps {
  searchId?: (params: SearchParameters) => Promise<number[]>;
  getFromId?: (offerId: number) => Promise<Job | null>;
  client?: BusinessFranceClient;
}

export async function task(
  params: SearchParameters,
  pool: DbPool,
  publish: (event: OfferEvent) => Promise<void> | void,
  options: { pageSize?: number; deps?: TaskDeps } = {},
): Promise<void> {
  const pageSize = options.pageSize ?? 25;
  const client = options.deps?.client ?? new BusinessFranceClient();
  const searchId = options.deps?.searchId ?? ((p) => client.searchId(p));
  const getFromId = options.deps?.getFromId ?? ((id) => client.getFromId(id));

  // Hash the API keys, not field names: matches Python's json.dumps(..., sort_keys=True).
  const scan = scanHash(params, { sortKeys: true });
  let offset = 0;

  // Replaying from zero is intentional: offset-based results can move between runs.
  while (offset < params.limit) {
    const size = Math.min(pageSize, params.limit - offset);
    const ids = await searchId({ ...params, skip: offset, limit: size });
    const events: OfferEvent[] = [];
    for (const identity of ids) {
      if (await seen(pool, String(identity))) {
        continue;
      }
      const job = await getFromId(identity);
      if (job === null) {
        continue;
      }
      events.push(normalize(job));
    }
    offset += ids.length;
    // Publish before recording: an unrecorded offer is published again next run.
    for (const event of events) {
      await publish(event);
    }
    await recordPage(
      pool,
      events,
      ids.map((id) => String(id)),
      scan,
      offset,
    );
    for (const event of events) {
      logger.info(
        `New offer: ${event.offer.title} in ${event.offer.country} at ${event.offer.organization}`,
      );
    }
    if (ids.length < size) {
      break;
    }
  }
  await requireRecentResults(pool, scan);
}
