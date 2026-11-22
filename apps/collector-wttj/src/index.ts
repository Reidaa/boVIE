import { logger } from "@bovie/cli-common";
import { recordPage, requireRecentResults, scanHash, seen } from "@bovie/collector-store";
import type { DbPool } from "@bovie/mysql-common";
import {
  createOfferEvent,
  type DisplayField,
  DisplayFieldSchema,
  type OfferEvent,
} from "@bovie/offer-events";
import { DetailResponseSchema, type JobDetail, SearchResponseSchema } from "./search.js";

export * from "./search.js";

export const API_URL = "https://api.welcometothejungle.com";
const PLACEHOLDER_TITLE = /^\$\d+$/;

export class HttpStatusError extends Error {
  readonly status: number;

  constructor(status: number, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.name = "HttpStatusError";
    this.status = status;
  }
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/**
 * Return the offer title, or null when WTTJ gives no usable title.
 *
 * WTTJ sometimes returns a "$1" placeholder as the name. The slug then still
 * holds the title before the first "_", e.g. "network-security-specialist_milan_ND_wZVZKeo".
 */
export function jobTitle(job: JobDetail): string | null {
  const trimmed = job.name.trim();
  if (!PLACEHOLDER_TITLE.test(trimmed)) {
    return trimmed.slice(0, 256);
  }
  const slugHead = (job.slug.split("_")[0] ?? "").replaceAll("-", " ").trim();
  if (!slugHead) {
    return null;
  }
  logger.warning(
    `WTTJ offer ${job.wttj_reference} has placeholder title ${JSON.stringify(job.name)}; using its slug`,
  );
  return `${slugHead[0]?.toUpperCase() ?? ""}${slugHead.slice(1)}`.slice(0, 256);
}

export function normalize(job: JobDetail, title: string): OfferEvent {
  const locationValue =
    job.offices
      .map((office) => `${office.city || "N/A"} (${office.country_code})`)
      .join(", ")
      .slice(0, 1024) || "N/A";

  const fields: DisplayField[] = [
    DisplayFieldSchema.parse({ name: "Entreprise", value: job.organization.name.slice(0, 1024) }),
    DisplayFieldSchema.parse({ name: "Lieu", value: locationValue }),
    DisplayFieldSchema.parse({ name: "Publié le", value: job.published_at.slice(0, 1024) }),
    DisplayFieldSchema.parse({ name: "Contrat", value: job.contract_type }),
  ];

  if (job.salary_min !== null || job.salary_max !== null) {
    fields.push(
      DisplayFieldSchema.parse({
        name: "Salaire",
        value: `${job.salary_min || "?"} – ${job.salary_max || "?"} ${job.salary_currency || ""} / ${job.salary_period || "N/A"}`,
      }),
    );
  }
  if (job.start_date) {
    fields.push(DisplayFieldSchema.parse({ name: "Début", value: job.start_date.slice(0, 1024) }));
  }
  if (
    job.apply_url &&
    (job.apply_url.startsWith("https://") || job.apply_url.startsWith("http://"))
  ) {
    fields.push(
      DisplayFieldSchema.parse({ name: "Candidature", value: job.apply_url.slice(0, 1024) }),
    );
  }

  const office = job.offices[0] ?? null;
  return createOfferEvent({
    type: "discovered",
    source: "wttj",
    source_offer_id: job.wttj_reference,
    offer: {
      title,
      organization: job.organization.name,
      country: office ? office.country_code : "N/A",
      city: office?.city ? office.city : "N/A",
      url: `https://www.welcometothejungle.com/fr/companies/${encodeURIComponent(job.organization.slug)}/jobs/${encodeURIComponent(job.slug)}`,
      fields,
    },
  });
}

export interface CollectOptions {
  query?: string;
  limit?: number;
  maxPages?: number;
  countries?: readonly string[];
  contracts?: readonly string[];
  baseUrl?: string;
  timeoutMs?: number;
  store?: {
    seen?: typeof seen;
    recordPage?: typeof recordPage;
    requireRecentResults?: typeof requireRecentResults;
  };
}

export async function collect(
  pool: DbPool,
  fetchFn: FetchLike,
  publish: (event: OfferEvent) => Promise<void> | void,
  options: CollectOptions = {},
): Promise<void> {
  const query = options.query ?? "";
  const limit = options.limit ?? 50;
  const maxPages = options.maxPages ?? 5;
  const countries = options.countries ?? [];
  const contracts = options.contracts ?? [];
  const baseUrl = (options.baseUrl ?? API_URL).replace(/\/$/, "");
  const timeoutMs = options.timeoutMs ?? 15_000;
  const checkSeen = options.store?.seen ?? seen;
  const savePage = options.store?.recordPage ?? recordPage;
  const checkRecent = options.store?.requireRecentResults ?? requireRecentResults;

  const scan = scanHash([query, [...countries], [...contracts], limit, maxPages]);

  let inspected = 0;

  // Restart at page 1 because ranked search results can move between invocations.
  for (let page = 1; page <= maxPages; page += 1) {
    const searchUrl = new URL(`${baseUrl}/api/v3/public/jobs`);
    searchUrl.searchParams.set("job_title", query);
    searchUrl.searchParams.set("page", String(page));

    const searchResponse = await fetchFn(searchUrl.toString(), {
      method: "GET",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!searchResponse.ok) {
      throw new HttpStatusError(searchResponse.status);
    }
    const result = SearchResponseSchema.parse(await searchResponse.json());
    if (result.metadata.page !== page) {
      throw new Error("WTTJ returned an unexpected page number");
    }

    const events: OfferEvent[] = [];
    const hits = result.data.slice(0, limit - inspected);

    for (const hit of hits) {
      inspected += 1;
      if (contracts.length > 0 && !contracts.includes(hit.contract_type)) {
        continue;
      }
      if (await checkSeen(pool, hit.reference)) {
        continue;
      }
      const detailUrl = `${baseUrl}/api/v3/organizations/${encodeURIComponent(hit.organization.slug)}/jobs/${encodeURIComponent(hit.slug)}`;
      const detailResponse = await fetchFn(detailUrl, {
        method: "GET",
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (detailResponse.status === 404 || detailResponse.status === 410) {
        logger.warning(`WTTJ offer ${hit.reference} is gone; skipping it`);
        continue;
      }
      if (!detailResponse.ok) {
        throw new HttpStatusError(detailResponse.status);
      }
      const job = DetailResponseSchema.parse(await detailResponse.json()).job;
      if (job.wttj_reference !== hit.reference) {
        throw new Error("WTTJ detail identity does not match its search result");
      }
      if (job.status !== "published") {
        continue;
      }
      if (contracts.length > 0 && !contracts.includes(job.contract_type)) {
        continue;
      }
      if (
        countries.length > 0 &&
        !job.offices.some((office) => countries.includes(office.country_code))
      ) {
        continue;
      }
      const title = jobTitle(job);
      if (title === null) {
        logger.warning(`WTTJ offer ${hit.reference} has no usable title; skipping it`);
        continue;
      }
      events.push(normalize(job, title));
    }

    // Publish before recording: an unrecorded offer is published again next run.
    for (const event of events) {
      await publish(event);
    }
    await savePage(
      pool,
      events,
      hits.map((hit) => hit.reference),
      scan,
      page,
    );
    for (const event of events) {
      logger.info(`New WTTJ offer: ${event.offer.title} at ${event.offer.organization}`);
    }
    if (inspected >= limit || result.data.length === 0 || page >= result.metadata.page_count) {
      break;
    }
  }

  await checkRecent(pool, scan);
}
