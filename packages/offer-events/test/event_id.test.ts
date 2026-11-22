import { describe, expect, test } from "bun:test";
import { createOfferEvent, type OfferEvent, type OfferEventInput } from "../src/index.js";

function makeEvent(offerId = "ABC", changes: Partial<OfferEventInput> = {}): OfferEvent {
  return createOfferEvent({
    type: "discovered",
    source: "business_france",
    source_offer_id: offerId,
    observed_at: new Date().toISOString(),
    offer: {
      title: "Engineer",
      organization: "Example",
      country: "France",
      city: "Paris",
      url: "https://example.com/jobs/abc",
      fields: [],
    },
    ...changes,
  });
}

describe("event IDs", () => {
  test("event IDs are stable across republishing", () => {
    const first = makeEvent();
    expect(makeEvent().event_id).toBe(first.event_id);
    expect(makeEvent("ABC", { observed_at: "2026-01-01T00:00:00Z" }).event_id).toBe(first.event_id);
    expect(makeEvent("other").event_id).not.toBe(first.event_id);
    expect(makeEvent("ABC", { type: "closed" }).event_id).not.toBe(first.event_id);
    expect(makeEvent("ABC", { source: "wttj" }).event_id).not.toBe(first.event_id);
  });

  test("update event IDs follow offer content", () => {
    const update = makeEvent("ABC", { type: "updated" });
    expect(makeEvent("ABC", { type: "updated" }).event_id).toBe(update.event_id);
    const changed = makeEvent("ABC", {
      type: "updated",
      offer: { ...update.offer, title: "Lead" },
    });
    expect(changed.event_id).not.toBe(update.event_id);
  });
});
