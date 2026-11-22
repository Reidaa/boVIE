// Source payloads that the end-to-end tests feed to the collectors.
import type { Job } from "@bovie/collector-business-france";

export function makeBfJob(identity: number, overrides: Partial<Job> = {}): Job {
  return {
    id: identity,
    missionTitle: "Engineer",
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
    contactEmail: "jobs@example.com",
    contactName: "Example",
    specializations: [],
    contactUrl: null,
    ...overrides,
  };
}

export function makeWttjHit(identity: string, contract = "vie") {
  return {
    reference: identity,
    slug: identity,
    contract_type: contract,
    organization: { name: "Example", slug: "example" },
  };
}

export function makeWttjDetail(identity: string, contract = "vie") {
  return {
    job: {
      wttj_reference: identity,
      slug: identity,
      name: "Engineer",
      contract_type: contract,
      status: "published",
      organization: { name: "Example", slug: "example" },
      offices: [{ city: "Montreal", country_code: "CA" }],
      published_at: "2026-09-01T00:00:00Z",
      salary_min: 2500,
    },
  };
}
