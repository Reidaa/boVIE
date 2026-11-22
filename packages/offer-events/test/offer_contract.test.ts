import { describe, expect, test } from "bun:test";
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { parseOfferEvent, parseOfferEventJson } from "../src/index.js";

const SAMPLES_DIR = resolve(import.meta.dirname, "contracts", "offer_event_v1");
const SAMPLES = readdirSync(SAMPLES_DIR)
  .filter((name) => name.endsWith(".json"))
  .sort()
  .map((name) => ({ name, path: join(SAMPLES_DIR, name) }));

describe("offer_event_v1 frozen contracts", () => {
  for (const sample of SAMPLES) {
    test(`published v1 message still parses: ${sample.name}`, () => {
      const bytes = readFileSync(sample.path);
      const parsed = parseOfferEventJson(bytes);
      expect(parsed.version).toBe(1);
    });

    test(`event_id stays stable: ${sample.name}`, () => {
      const stored = JSON.parse(readFileSync(sample.path, "utf8")) as Record<string, unknown>;
      const storedId = String(stored.event_id);
      delete stored.event_id;
      const derived = parseOfferEvent(stored);
      expect(derived.event_id).toBe(storedId);
    });
  }

  test("samples cover every event type", () => {
    const types = new Set(
      SAMPLES.map(
        (sample) => (JSON.parse(readFileSync(sample.path, "utf8")) as { type: string }).type,
      ),
    );
    expect(types).toEqual(new Set(["discovered", "updated", "closed"]));
  });

  test("unknown top-level fields are rejected", () => {
    const sample = JSON.parse(readFileSync(SAMPLES[0]!.path, "utf8")) as Record<string, unknown>;
    expect(() => parseOfferEvent({ ...sample, unexpected: true })).toThrow();
  });
});
