import { describe, expect, test } from "bun:test";
import { displayFields, type Job } from "../src/index.js";

function makeBfJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 123,
    missionTitle: "Software Engineer",
    missionStartDate: "2026-06-01T00:00:00",
    missionEndDate: "2027-06-01T00:00:00",
    creationDate: "2026-05-31T00:00:00",
    missionDuration: 12,
    activitySectorN1: "Tech",
    organizationName: "Example Corp",
    countryName: "Canada",
    cityName: "Montreal",
    cityAffectation: "Montreal",
    indemnite: 2500,
    contactEmail: "jobs@example.com",
    contactName: "Jane Doe",
    specializations: [],
    contactUrl: null,
    ...overrides,
  };
}

describe("business france display fields", () => {
  test("displays job specializations and default Business France application", () => {
    const job = makeBfJob({
      specializations: [
        {
          id: "24",
          specializationLabel: "SYSTEMES ET LOGICIELS INFORMATIQUES",
          specializationLabelEn: "INFORMATION SYSTEMS",
          parentId: null,
        },
        {
          id: "216",
          specializationLabel: "MARKETING - COMMUNICATION",
          specializationLabelEn: "MARKETING COMMUNICATION",
          parentId: null,
        },
      ],
    });

    const fields = displayFields(job);
    expect(fields).toContainEqual({
      inline: true,
      name: ":label: Specialization(s)",
      value: "SYSTEMES ET LOGICIELS INFORMATIQUES, MARKETING - COMMUNICATION",
    });
    expect(fields).toContainEqual({
      inline: true,
      name: ":outbox_tray: Application",
      value: "Business France",
    });
  });

  test("displays external application link", () => {
    const applicationUrl = "https://prose.com/careers?ashby_jid=d93116e8";
    const fields = displayFields(makeBfJob({ contactUrl: applicationUrl }));
    expect(fields).toContainEqual({
      inline: true,
      name: ":outbox_tray: Application",
      value: `[Site externe](${applicationUrl})`,
    });
  });
});
