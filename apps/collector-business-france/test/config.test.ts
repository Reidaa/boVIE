import { describe, expect, test } from "bun:test";
import { configFromParams } from "../src/index.js";

describe("business france config", () => {
  test("configFromParams resolves regions and specializations", () => {
    const config = configFromParams({
      limit: 100,
      regions: ["AMERIQUE DU NORD"],
      specializations: ["Information Systems"],
      countries: [],
    });

    expect(config.search.limit).toBe(100);
    expect(config.search.specializations.length).toBe(1);
    expect(config.search.countries.length).toBe(3);
  });

  test("invalid region throws", () => {
    expect(() =>
      configFromParams({
        limit: 100,
        regions: ["Invalid Region"],
        specializations: ["Information Systems"],
        countries: ["Germany", "Canada"],
      }),
    ).toThrow(/Invalid geographic zone/);
  });

  test("invalid specialization throws", () => {
    expect(() =>
      configFromParams({
        limit: 100,
        regions: ["AMERIQUE DU NORD"],
        specializations: ["Invalid Specialization"],
        countries: ["Germany", "Canada"],
      }),
    ).toThrow(/Invalid specialization/);
  });

  test("invalid country throws", () => {
    expect(() =>
      configFromParams({
        limit: 100,
        regions: ["AMERIQUE DU NORD"],
        specializations: ["Information Systems"],
        countries: ["Invalid Country"],
      }),
    ).toThrow(/Invalid country/);
  });

  test("invalid limit throws", () => {
    expect(() =>
      configFromParams({
        limit: -10,
        regions: ["AMERIQUE DU NORD"],
        specializations: ["Information Systems"],
        countries: [],
      }),
    ).toThrow();
  });

  test("search IDs are sorted", () => {
    const config = configFromParams({
      limit: 10,
      regions: ["Europe Occidentale", "Asie et Pacifique"],
      specializations: ["Information Systems", "Business", "Marketing Communication"],
      countries: [],
    });

    expect(config.search.countries).toEqual([...config.search.countries].sort());
    expect(config.search.specializations).toEqual([...config.search.specializations].sort());
  });
});
