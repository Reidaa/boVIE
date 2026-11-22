import { z } from "zod";
import {
  getCountriesIdByGeographicZone,
  getCountryCodeFromName,
  getCountryIds,
  getCountryNames,
  getSpecializationIdFromName,
  getSpecializationNames,
  getZoneIdFromName,
  getZoneNames,
} from "./datasets.js";

export const SearchConfigSchema = z.object({
  limit: z.number().int().positive(),
  countries: z.array(z.string()).default([]),
  specializations: z.array(z.string()).default([]),
});

export type SearchConfig = z.infer<typeof SearchConfigSchema>;

export interface Config {
  readonly search: SearchConfig;
}

export function parseSearch(params: {
  limit: number;
  regions: Iterable<string>;
  specializations: Iterable<string>;
  countries: Iterable<string>;
}): SearchConfig {
  const specializationIds = new Set<string>();
  const countryIds = new Set<string>();
  const validSpecNames = new Set(getSpecializationNames());
  const validZoneNames = new Set(getZoneNames());
  const validCountryIds = new Set(getCountryIds());
  const validCountryNamesLower = new Set(getCountryNames().map((name) => name.toLowerCase()));

  for (const spe of params.specializations) {
    if (!validSpecNames.has(spe.toLowerCase())) {
      throw new Error(`Invalid specialization: ${spe}`);
    }
    const speId = getSpecializationIdFromName(spe);
    if (speId === null) {
      throw new Error(`Invalid specialization: ${spe}`);
    }
    specializationIds.add(speId);
  }

  for (const region of params.regions) {
    if (!validZoneNames.has(region.toLowerCase())) {
      throw new Error(`Invalid geographic zone: ${region}`);
    }
    const zoneId = getZoneIdFromName(region);
    if (zoneId === null) {
      throw new Error(`Invalid geographic zone: ${region}`);
    }
    for (const countryId of getCountriesIdByGeographicZone(zoneId)) {
      if (!validCountryIds.has(countryId)) {
        throw new Error(`Invalid country from preset: ${countryId}`);
      }
      countryIds.add(countryId);
    }
  }

  for (const country of params.countries) {
    if (!validCountryNamesLower.has(country.toLowerCase())) {
      throw new Error(`Invalid country: ${country}`);
    }
    const countryId = getCountryCodeFromName(country);
    if (countryId === null) {
      throw new Error(`Invalid country: ${country}`);
    }
    countryIds.add(countryId);
  }

  // Sorted, not set order: the collector hashes the search into its checkpoint key.
  return SearchConfigSchema.parse({
    limit: params.limit,
    specializations: Array.from(specializationIds).sort(),
    countries: Array.from(countryIds).sort(),
  });
}

export function configFromParams(params: {
  limit: number;
  regions: Iterable<string>;
  specializations: Iterable<string>;
  countries: Iterable<string>;
}): Config {
  return {
    search: parseSearch(params),
  };
}
