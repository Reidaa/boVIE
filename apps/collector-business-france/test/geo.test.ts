import { describe, expect, test } from "bun:test";
import { getZoneIdFromName, getZoneNames } from "../src/index.js";

describe("business france geographic zones", () => {
  test("getZoneNames returns all 8 zones", () => {
    const expected = [
      "afrique du nord",
      "afrique subsaharienne",
      "amerique du nord",
      "amerique latine",
      "asie et pacifique",
      "europe occidentale",
      "europe centrale et orientale",
      "proche et moyen orient",
    ];
    expect(getZoneNames().sort()).toEqual(expected.sort());
  });

  test("getZoneIdFromName matches lowercase name", () => {
    expect(getZoneIdFromName("afrique du nord")).toBe("7");
  });

  test("getZoneIdFromName matches mixed case", () => {
    expect(getZoneIdFromName("EUROPE OCCIDenTALE")).toBe("5");
  });
});
