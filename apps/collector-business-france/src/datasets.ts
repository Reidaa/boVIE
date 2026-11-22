import countriesRaw from "./data/countries.json" with { type: "json" };
import geozonesRaw from "./data/geozones.json" with { type: "json" };
import specializationsRaw from "./data/specializations.json" with { type: "json" };

export interface Country {
  readonly countryId: string;
  readonly name: string;
  readonly geographicZoneId: string;
}

export interface GeographicZone {
  readonly id: string;
  readonly name: string;
}

export interface Specialization {
  readonly id: string;
  readonly specializationLabel: string;
  readonly specializationLabelEn: string;
  readonly parentId: number | null;
}

export const COUNTRIES: readonly Country[] = countriesRaw.map((item) => ({
  countryId: item.countryId,
  name: item.countryNameEn,
  geographicZoneId: item.geographicZoneId,
}));

export const ZONES: readonly GeographicZone[] = geozonesRaw.map((item) => ({
  id: item.geographicZoneId,
  name: item.geographicZoneLabelEn,
}));

export const SPECIALIZATIONS: readonly Specialization[] = specializationsRaw.map((item) => ({
  id: item.specializationId,
  specializationLabel: item.specializationLabel,
  specializationLabelEn: item.specializationLabelEn,
  parentId: item.specializationParentId,
}));

export function getCountriesIdByGeographicZone(zoneId: number | string): string[] {
  const zoneStr = String(zoneId);
  return COUNTRIES.filter((c) => c.geographicZoneId === zoneStr).map((c) => c.countryId);
}

export function getCountryNames(): string[] {
  return COUNTRIES.map((c) => c.name);
}

export function getCountryIds(): string[] {
  return COUNTRIES.map((c) => c.countryId);
}

export function getCountryCodeFromName(countryName: string): string | null {
  const nameLower = countryName.toLowerCase();
  const found = COUNTRIES.find((c) => c.name.toLowerCase() === nameLower);
  return found ? found.countryId : null;
}

export function getZoneNames(): string[] {
  return ZONES.map((z) => z.name.toLowerCase());
}

export function getZoneIdFromName(name: string): string | null {
  const nameNorm = name.trim().toLowerCase();
  const found = ZONES.find((z) => z.name.toLowerCase() === nameNorm);
  return found ? found.id : null;
}

export function getSpecializationNames(): string[] {
  return SPECIALIZATIONS.map((s) => s.specializationLabelEn.toLowerCase());
}

export function getSpecializationIdFromName(name: string): string | null {
  const nameNorm = name.trim().toLowerCase();
  const found = SPECIALIZATIONS.find((s) => s.specializationLabelEn.toLowerCase() === nameNorm);
  return found ? found.id : null;
}
