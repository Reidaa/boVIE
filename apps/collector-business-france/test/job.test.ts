import { describe, expect, test } from "bun:test";
import { externalApplicationUrl, parseJob } from "../src/index.js";

describe("business france job model", () => {
  test("detects external application URL", () => {
    const url = "https://prose.com/careers?ashby_jid=d93116e8";
    expect(externalApplicationUrl({ contactUrl: url })).toBe(url);
  });

  test("ignores internal application URL", () => {
    expect(
      externalApplicationUrl({
        contactUrl: "https://mon-vie-via.businessfrance.fr/offres/244342",
      }),
    ).toBeNull();
  });

  test("ignores empty application URL", () => {
    expect(externalApplicationUrl({ contactUrl: "" })).toBeNull();
  });

  test("ignores unused API fields and sanitizes contactName", () => {
    const payload = {
      id: 1,
      missionTitle: " Engineer ",
      organizationName: "Example",
      countryName: "Canada",
      cityName: "Montreal",
      cityAffectation: "Montreal",
      missionStartDate: "2026-06-01",
      missionEndDate: "2027-06-01",
      creationDate: "2026-05-01",
      missionDuration: 12,
      activitySectorN1: "Tech",
      indemnite: 2500,
      contactEmail: null,
      contactName: null,
      specializations: null,
      viewCounter: "unexpected",
    };

    const job = parseJob(payload);
    expect(job.missionTitle).toBe("Engineer");
    expect(job.contactName).toBe("X");
  });
});
