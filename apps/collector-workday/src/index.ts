import { logger } from "@bovie/cli-common";
import {
  recordPage,
  requireRecentResults,
  SourceSilent,
  scanHash,
  seen,
} from "@bovie/collector-store";
import type { DbPool } from "@bovie/mysql-common";
import {
  createOfferEvent,
  type DisplayField,
  DisplayFieldSchema,
  type OfferEvent,
} from "@bovie/offer-events";
import { ZodError } from "zod";
import {
  type Board,
  BoardSchema,
  DetailResponseSchema,
  type JobDetail,
  SearchResponseSchema,
} from "./api.js";

export * from "./api.js";

// Workday rejects a larger page with 400.
export const PAGE_SIZE = 20;

export class HttpStatusError extends Error {
  readonly status: number;

  constructor(status: number, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.name = "HttpStatusError";
    this.status = status;
  }
}

// A request that failed before its whole response arrived: refused, timed out, or cut off.
export class TransportError extends Error {
  constructor(url: string, cause: unknown) {
    super(`Request to ${url} failed`, { cause });
    this.name = "TransportError";
  }
}

export class CollectionFailed extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CollectionFailed";
  }
}

export class BoardValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BoardValidationError";
  }
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/**
 * Parse the JSON list of boards from WORKDAY_BOARDS; it must not be empty.
 */
export function loadBoards(text: string): Board[] {
  if (!text.trim()) {
    throw new BoardValidationError("WORKDAY_BOARDS must be a JSON list of at least one board");
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    throw new BoardValidationError(
      `WORKDAY_BOARDS must be valid JSON: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  let boards: Board[];
  try {
    boards = BoardSchema.array().parse(parsed);
  } catch (error) {
    throw new BoardValidationError(
      `Invalid WORKDAY_BOARDS: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  if (boards.length === 0) {
    throw new BoardValidationError("WORKDAY_BOARDS must be a JSON list of at least one board");
  }
  return boards;
}

export function normalize(board: Board, externalPath: string, job: JobDetail): OfferEvent {
  const locations = [job.location, ...job.additionalLocations].filter((item): item is string =>
    Boolean(item),
  );
  const fields: DisplayField[] = [
    DisplayFieldSchema.parse({ name: "Entreprise", value: board.company.slice(0, 1024) }),
    DisplayFieldSchema.parse({
      name: "Lieu",
      value: locations.join(", ").slice(0, 1024) || "N/A",
    }),
  ];

  const optionalFields: Array<[string, string | null]> = [
    ["Publié le", job.startDate],
    ["Contrat", job.timeType],
    ["Date limite", job.endDate],
    ["Référence", job.jobReqId],
  ];
  for (const [name, value] of optionalFields) {
    if (value) {
      fields.push(DisplayFieldSchema.parse({ name, value: value.slice(0, 1024) }));
    }
  }

  const country = job.jobRequisitionLocation?.country?.alpha2Code ?? null;
  return createOfferEvent({
    type: "discovered",
    source: "workday",
    source_offer_id: `${board.name}/${job.jobPostingId}`,
    offer: {
      title: job.title.trim().slice(0, 256),
      organization: board.company,
      country: country || "N/A",
      city: job.location || "N/A",
      url: `${board.origin}/${board.site}${externalPath}`,
      fields,
    },
  });
}

const defaultSleep = (seconds: number): Promise<void> =>
  seconds > 0 ? new Promise((resolve) => setTimeout(resolve, seconds * 1000)) : Promise.resolve();

export interface WorkdayCollectOptions {
  limit?: number;
  delay?: number;
  timeoutMs?: number;
  sleep?: (seconds: number) => Promise<void>;
  store?: {
    seen?: typeof seen;
    recordPage?: typeof recordPage;
    requireRecentResults?: typeof requireRecentResults;
  };
}

class WorkdayDetailMismatchError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkdayDetailMismatchError";
  }
}

export async function collectBoard(
  pool: DbPool,
  fetchFn: FetchLike,
  publish: (event: OfferEvent) => Promise<void> | void,
  board: Board,
  options: WorkdayCollectOptions = {},
): Promise<void> {
  const limit = options.limit ?? 40;
  const delay = options.delay ?? 1.0;
  const timeoutMs = options.timeoutMs ?? 15_000;
  const sleep = options.sleep ?? defaultSleep;
  const checkSeen = options.store?.seen ?? seen;
  const savePage = options.store?.recordPage ?? recordPage;
  const checkRecent = options.store?.requireRecentResults ?? requireRecentResults;

  const scan = scanHash([board.apiUrl, board.searchText, board.appliedFacets, limit], {
    sortKeys: true,
  });

  // Read the whole body here, so a connection lost mid-body also fails only this board.
  const request = async (url: string, init: RequestInit) => {
    try {
      const response = await fetchFn(url, init);
      return { status: response.status, ok: response.ok, body: await response.text() };
    } catch (cause) {
      throw new TransportError(url, cause);
    }
  };

  let inspected = 0;
  let offset = 0;
  let total: number | null = null;

  // Restart at offset 0 each run: the newest postings come first.
  while (inspected < limit) {
    await sleep(delay);
    const listResponse = await request(`${board.apiUrl}/jobs`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        limit: PAGE_SIZE,
        offset,
        searchText: board.searchText,
        appliedFacets: board.appliedFacets,
      }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!listResponse.ok) {
      throw new HttpStatusError(listResponse.status);
    }
    const result = SearchResponseSchema.parse(JSON.parse(listResponse.body));
    if (total === null) {
      total = result.total;
    }

    const postings = result.jobPostings.slice(0, limit - inspected);
    inspected += postings.length;
    const events: OfferEvent[] = [];

    for (const posting of postings) {
      if (await checkSeen(pool, `${board.name}/${posting.jobId}`)) {
        continue;
      }
      await sleep(delay);
      const detailResponse = await request(`${board.apiUrl}${posting.externalPath}`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (detailResponse.status === 404 || detailResponse.status === 410) {
        logger.warning(`Workday job ${posting.jobId} is gone; skipping it`);
        continue;
      }
      if (!detailResponse.ok) {
        throw new HttpStatusError(detailResponse.status);
      }
      const job = DetailResponseSchema.parse(JSON.parse(detailResponse.body)).jobPostingInfo;
      if (job.jobPostingId !== posting.jobId) {
        throw new WorkdayDetailMismatchError("Workday detail identity does not match its posting");
      }
      if (!job.posted) {
        continue;
      }
      events.push(normalize(board, posting.externalPath, job));
    }

    // Publish before recording: an unrecorded offer is published again next run.
    for (const event of events) {
      await publish(event);
    }
    await savePage(
      pool,
      events,
      postings.map((posting) => `${board.name}/${posting.jobId}`),
      scan,
      offset,
    );
    for (const event of events) {
      logger.info(`New Workday offer: ${event.offer.title} at ${event.offer.organization}`);
    }
    offset += result.jobPostings.length;
    // Workday serves the first page again past the end, so stop at `total`.
    if (result.jobPostings.length < PAGE_SIZE || offset >= total) {
      break;
    }
  }

  await checkRecent(pool, scan);
}

function isBoardIsolatedError(error: unknown): boolean {
  return (
    error instanceof HttpStatusError ||
    error instanceof TransportError ||
    error instanceof ZodError ||
    error instanceof SourceSilent ||
    error instanceof WorkdayDetailMismatchError ||
    error instanceof SyntaxError ||
    (error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError"))
  );
}

/**
 * Collect every board, then throw CollectionFailed if any of them failed.
 *
 * A board fails alone on HTTP, response-shape or silent-source errors. Broker and
 * database errors affect every board, so they stop the run at once.
 */
export async function collect(
  pool: DbPool,
  fetchFn: FetchLike,
  publish: (event: OfferEvent) => Promise<void> | void,
  boards: readonly Board[],
  options: WorkdayCollectOptions = {},
): Promise<void> {
  const failed: string[] = [];
  for (const board of boards) {
    try {
      await collectBoard(pool, fetchFn, publish, board, options);
    } catch (error) {
      if (!isBoardIsolatedError(error)) {
        throw error;
      }
      logger.exception(`Workday board ${board.name} failed`, error);
      failed.push(board.name);
    }
  }
  if (failed.length > 0) {
    throw new CollectionFailed(`Workday boards failed: ${failed.join(", ")}`);
  }
}
