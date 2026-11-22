import { describe, expect, test } from "bun:test";
import { getCountriesIdByGeographicZone, getZoneIdFromName } from "../src/index.js";

describe("business france countries", () => {
  test("getCountriesIdByGeographicZone from numeric ID", () => {
    expect(getCountriesIdByGeographicZone(2).sort()).toEqual(["BS", "CA", "US"]);
  });

  test("getCountriesIdByGeographicZone from zone name", () => {
    const zoneId = getZoneIdFromName("Amerique du Nord");
    expect(zoneId).not.toBeNull();
    expect(getCountriesIdByGeographicZone(zoneId!).sort()).toEqual(["BS", "CA", "US"]);
  });
});
