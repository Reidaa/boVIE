import { logger } from "@bovie/cli-common";
import { z } from "zod";
import type { Specialization } from "./datasets.js";

export const API_URL = "https://civiweb-api-prd.azurewebsites.net/api/Offers";
export const PUBLIC_OFFERS_URL = "https://mon-vie-via.businessfrance.fr/offres";

export const BUSINESS_FRANCE_HOSTS = new Set([
  "businessfrance.fr",
  "mon-vie-via.businessfrance.fr",
  "civiweb-api-prd.azurewebsites.net",
]);

export class HttpStatusError extends Error {
  readonly status: number;

  constructor(status: number, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.name = "HttpStatusError";
    this.status = status;
  }
}

export interface SearchParameters {
  activitySectorId: number[];
  companiesSizes: string[];
  countriesIds: string[];
  entreprisesIds: number[];
  geographicZones: string[];
  missionsDurations: string[];
  missionsTypesIds: string[];
  specializationsIds: string[];
  studiesLevelId: string[];
  missionStartDate: string | null;
  limit: number;
  query: string;
  skip: number;
}

export function createSearchParameters(
  overrides: Partial<SearchParameters> = {},
): SearchParameters {
  return {
    activitySectorId: [],
    companiesSizes: [],
    countriesIds: [],
    entreprisesIds: [],
    geographicZones: [],
    missionsDurations: [],
    missionsTypesIds: [],
    specializationsIds: [],
    studiesLevelId: [],
    missionStartDate: null,
    limit: 10,
    query: "",
    skip: 0,
    ...overrides,
  };
}

const SpecializationApiSchema = z.object({
  specializationId: z.string(),
  specializationLabel: z.string(),
  specializationLabelEn: z.string(),
  specializationParentId: z.number().int().nullable(),
});

const JobApiSchema = z.object({
  activitySectorN1: z.string().nullable(),
  cityAffectation: z.string(),
  cityName: z.string().nullable(),
  contactEmail: z.string().nullable(),
  contactName: z.string().nullable(),
  countryName: z.string(),
  creationDate: z.string(),
  id: z.number().int(),
  indemnite: z.number(),
  missionDuration: z.number().int(),
  missionEndDate: z.string(),
  missionStartDate: z.string(),
  missionTitle: z.string(),
  organizationName: z.string(),
  specializations: z.array(SpecializationApiSchema).nullable(),
  contactURL: z.string().nullable().optional(),
});

export interface Job {
  readonly activitySectorN1: string | null;
  readonly cityAffectation: string;
  readonly cityName: string | null;
  readonly contactEmail: string | null;
  readonly contactName: string | null;
  readonly countryName: string;
  readonly creationDate: string;
  readonly id: number;
  readonly indemnite: number;
  readonly missionDuration: number;
  readonly missionEndDate: string;
  readonly missionStartDate: string;
  readonly missionTitle: string;
  readonly organizationName: string;
  readonly specializations: readonly Specialization[] | null;
  readonly contactUrl: string | null;
}

function trimNullable(value: string | null | undefined): string | null {
  return value === null || value === undefined ? null : value.trim();
}

function sanitizeContactName(value: string | null): string {
  if (value === null) {
    return "X";
  }
  const cleaned = value.replaceAll("Monsieur", "").replaceAll("Madame", "").trim();
  return cleaned === "" ? "XXX" : cleaned;
}

export function parseJob(raw: unknown): Job {
  const parsed = JobApiSchema.parse(raw);
  return {
    activitySectorN1: trimNullable(parsed.activitySectorN1),
    cityAffectation: parsed.cityAffectation.trim(),
    cityName: trimNullable(parsed.cityName),
    contactEmail: trimNullable(parsed.contactEmail),
    contactName: sanitizeContactName(trimNullable(parsed.contactName)),
    countryName: parsed.countryName.trim(),
    creationDate: parsed.creationDate.trim(),
    id: parsed.id,
    indemnite: parsed.indemnite,
    missionDuration: parsed.missionDuration,
    missionEndDate: parsed.missionEndDate.trim(),
    missionStartDate: parsed.missionStartDate.trim(),
    missionTitle: parsed.missionTitle.trim(),
    organizationName: parsed.organizationName.trim(),
    specializations: parsed.specializations
      ? parsed.specializations.map((s) => ({
          id: s.specializationId,
          specializationLabel: s.specializationLabel,
          specializationLabelEn: s.specializationLabelEn,
          parentId: s.specializationParentId,
        }))
      : null,
    contactUrl: trimNullable(parsed.contactURL),
  };
}

export function externalApplicationUrl(job: Pick<Job, "contactUrl">): string | null {
  if (!job.contactUrl) {
    return null;
  }
  let parsed: URL;
  try {
    parsed = new URL(job.contactUrl);
  } catch {
    return null;
  }
  if ((parsed.protocol !== "http:" && parsed.protocol !== "https:") || !parsed.hostname) {
    return null;
  }
  const hostname = parsed.hostname.replace(/^www\./, "");
  if (BUSINESS_FRANCE_HOSTS.has(hostname)) {
    return null;
  }
  return job.contactUrl;
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class BusinessFranceClient {
  private readonly fetchFn: FetchLike;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  apiKey: string | null = null;

  constructor(options: { fetchFn?: FetchLike; baseUrl?: string; timeoutMs?: number } = {}) {
    this.fetchFn = options.fetchFn ?? ((input, init) => fetch(input, init));
    this.baseUrl = options.baseUrl ?? API_URL;
    this.timeoutMs = options.timeoutMs ?? 10_000;
  }

  async publicApiKey(): Promise<string> {
    const response = await this.fetchFn(PUBLIC_OFFERS_URL, {
      method: "GET",
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!response.ok) {
      throw new HttpStatusError(response.status);
    }
    const text = await response.text();
    const match = /API_KEY:"((?:[^"\\]|\\.)*)"/.exec(text);
    if (!match) {
      throw new Error("Business France site no longer publishes an API key");
    }
    return JSON.parse(`"${match[1]}"`) as string;
  }

  async request(method: string, path: string, body?: unknown): Promise<Response> {
    if (this.apiKey === null) {
      this.apiKey = process.env.BUSINESS_FRANCE_API_KEY || (await this.publicApiKey());
    }
    const url = `${this.baseUrl}${path}`;
    const send = async (key: string): Promise<Response> => {
      const headers: Record<string, string> = { "X-API-KEY": key };
      const init: RequestInit = {
        method,
        headers,
        signal: AbortSignal.timeout(this.timeoutMs),
      };
      if (body !== undefined) {
        headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(body);
      }
      return await this.fetchFn(url, init);
    };

    let response = await send(this.apiKey);
    if (response.status === 401) {
      logger.info("Refreshing the Business France API key");
      this.apiKey = await this.publicApiKey();
      response = await send(this.apiKey);
    }
    return response;
  }

  async getFromId(offerId: number): Promise<Job | null> {
    try {
      const response = await this.request("GET", `/details/${offerId}`);
      if (response.status === 404 || response.status === 410) {
        logger.warning(`Business France offer ${offerId} is gone; skipping it`);
        return null;
      }
      if (!response.ok) {
        throw new HttpStatusError(response.status);
      }
      return parseJob(await response.json());
    } catch (error) {
      logger.exception(`Failed to fetch Business France offer ${offerId}`, error);
      throw error;
    }
  }

  async searchId(params: SearchParameters): Promise<number[]> {
    logger.debug(`Searching offers with parameters: ${JSON.stringify(params)}`);
    try {
      const response = await this.request("POST", "/search", params);
      if (!response.ok) {
        throw new HttpStatusError(response.status);
      }
      const data = (await response.json()) as { result: Array<{ id: number | string }> };
      return data.result.map((entry) => Number(entry.id));
    } catch (error) {
      logger.exception("Failed to search Business France offers", error);
      throw error;
    }
  }
}
