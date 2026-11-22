import { describe, expect, test } from "bun:test";
import { SourceSilent } from "@bovie/collector-store";
import { collect, DetailResponseSchema, HttpStatusError, normalize } from "@bovie/collector-wttj";
import type { DbPool, RowDataPacket } from "@bovie/mysql-common";
import type { OfferEvent } from "@bovie/offer-events";
import { createTestDbContext, getMysqlAdminUrl, jsonResponse } from "./helpers/db.js";

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

const noopStore = {
  seen: async () => false,
  recordPage: async () => {},
  requireRecentResults: async () => {},
};

describe("wttj collector", () => {
  test.skipIf(!getMysqlAdminUrl())("pagination, filtering, and detail normalization", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("collector");
      const paths: string[] = [];
      const published: OfferEvent[] = [];

      const fetchFn = async (input: string) => {
        const url = new URL(input);
        paths.push(url.pathname);
        if (url.pathname.endsWith("/public/jobs")) {
          expect(url.searchParams.get("job_title")).toBe("");
          const page = Number(url.searchParams.get("page"));
          return jsonResponse({
            data:
              page === 1
                ? [makeWttjHit("first"), makeWttjHit("full-time", "full_time")]
                : [makeWttjHit("second")],
            metadata: { page, page_count: 2, per_page: 2, total: 3 },
          });
        }
        const slug = url.pathname.split("/").pop() ?? "";
        return jsonResponse(makeWttjDetail(slug, slug === "full-time" ? "full_time" : "vie"));
      };

      await collect(
        pool,
        fetchFn,
        (e) => {
          published.push(e);
        },
        { baseUrl: "https://example.invalid", limit: 10, maxPages: 5 },
      );
      await collect(
        pool,
        fetchFn,
        (e) => {
          published.push(e);
        },
        { baseUrl: "https://example.invalid", limit: 10, maxPages: 5 },
      );

      expect(published.map((e) => e.source_offer_id)).toEqual(["first", "full-time", "second"]);

      const [[countRow]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM offers",
      );
      expect(Number(countRow?.count)).toBe(3);

      const [[seenRow]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM offers WHERE last_seen_at IS NOT NULL",
      );
      expect(Number(seenRow?.count)).toBe(3);

      const [[firstRow]] = await pool.execute<RowDataPacket[]>(
        "SELECT payload FROM offers WHERE source_offer_id = ?",
        ["first"],
      );
      const payload =
        typeof firstRow?.payload === "string" ? JSON.parse(firstRow.payload) : firstRow?.payload;
      expect(payload.source).toBe("wttj");
      expect(payload.offer.country).toBe("CA");

      expect(paths.filter((p) => p.endsWith("/full-time")).length).toBe(1);
      expect(paths.filter((p) => p.endsWith("/first")).length).toBe(1);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("failed detail does not commit page", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("collector");
      const published: OfferEvent[] = [];
      const fetchFn = async (input: string) => {
        const url = new URL(input);
        if (url.pathname.endsWith("/public/jobs")) {
          return jsonResponse({
            data: [makeWttjHit("first"), makeWttjHit("second")],
            metadata: { page: 1, page_count: 1 },
          });
        }
        if (url.pathname.endsWith("second")) {
          return new Response(null, { status: 503 });
        }
        return jsonResponse(makeWttjDetail("first"));
      };

      await expect(
        collect(
          pool,
          fetchFn,
          (e) => {
            published.push(e);
          },
          { baseUrl: "https://example.invalid" },
        ),
      ).rejects.toBeInstanceOf(HttpStatusError);

      expect(published).toEqual([]);
      const [[offers]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM offers");
      const [[cps]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM checkpoints",
      );
      expect(Number(offers?.count)).toBe(0);
      expect(Number(cps?.count)).toBe(0);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())(
    "offer removed before its details are read is skipped",
    async () => {
      const ctx = await createTestDbContext();
      try {
        const pool = await ctx.create("collector");
        const published: OfferEvent[] = [];
        const fetchFn = async (input: string) => {
          const url = new URL(input);
          if (url.pathname.endsWith("/public/jobs")) {
            return jsonResponse({
              data: [makeWttjHit("first"), makeWttjHit("second")],
              metadata: { page: 1, page_count: 1 },
            });
          }
          if (url.pathname.endsWith("first")) {
            return new Response(null, { status: 404 });
          }
          return jsonResponse(makeWttjDetail("second"));
        };

        await collect(
          pool,
          fetchFn,
          (e) => {
            published.push(e);
          },
          { baseUrl: "https://example.invalid" },
        );
        expect(published.map((e) => e.source_offer_id)).toEqual(["second"]);
      } finally {
        await ctx.cleanup();
      }
    },
  );

  for (const contract of [
    "full_time",
    "part_time",
    "temporary",
    "internship",
    "apprenticeship",
    "freelance",
    "vie",
    "future_contract_type",
  ]) {
    test(`all contract types are collected by default (${contract})`, async () => {
      const recorded: OfferEvent[] = [];
      const fetchFn = async (input: string) => {
        const url = new URL(input);
        if (url.pathname.endsWith("/public/jobs")) {
          expect(url.searchParams.get("job_title")).toBe("");
          expect(url.searchParams.has("contract_type")).toBe(false);
          return jsonResponse({
            data: [makeWttjHit("job", contract)],
            metadata: { page: 1, page_count: 1 },
          });
        }
        return jsonResponse(makeWttjDetail("job", contract));
      };

      await collect(
        {} as DbPool,
        fetchFn,
        (e) => {
          recorded.push(e);
        },
        { baseUrl: "https://example.invalid", store: noopStore },
      );

      expect(recorded.length).toBe(1);
      expect(recorded[0]?.source_offer_id).toBe("job");
      const contratField = recorded[0]?.offer.fields.find((f) => f.name === "Contrat");
      expect(contratField?.value).toBe(contract);
    });
  }

  test("optional filters and publication status", async () => {
    const recorded: OfferEvent[] = [];
    const fetched: string[] = [];

    const fetchFn = async (input: string) => {
      const url = new URL(input);
      if (url.pathname.endsWith("/public/jobs")) {
        expect(url.searchParams.get("job_title")).toBe("engineer");
        return jsonResponse({
          data: [
            makeWttjHit("selected", "full_time"),
            makeWttjHit("intern", "internship"),
            makeWttjHit("excluded", "vie"),
            makeWttjHit("changed", "full_time"),
            makeWttjHit("draft", "full_time"),
            makeWttjHit("abroad", "full_time"),
            makeWttjHit("seen", "full_time"),
          ],
          metadata: { page: 1, page_count: 1 },
        });
      }
      const identity = url.pathname.split("/").pop() ?? "";
      fetched.push(identity);
      const payload = makeWttjDetail(identity, identity === "intern" ? "internship" : "full_time");
      if (identity === "changed") {
        payload.job.contract_type = "vie";
      }
      if (identity === "draft") {
        payload.job.status = "draft";
      }
      if (identity === "abroad") {
        payload.job.offices = [{ city: "Paris", country_code: "FR" }];
      }
      if (identity === "selected") {
        payload.job.offices.unshift({ city: "Paris", country_code: "FR" });
      }
      return jsonResponse(payload);
    };

    await collect(
      {} as DbPool,
      fetchFn,
      (e) => {
        recorded.push(e);
      },
      {
        baseUrl: "https://example.invalid",
        query: "engineer",
        countries: ["CA"],
        contracts: ["full_time", "internship"],
        store: {
          ...noopStore,
          seen: async (_pool, identity) => identity === "seen",
        },
      },
    );

    expect(recorded.map((e) => e.source_offer_id)).toEqual(["selected", "intern"]);
    expect(fetched).not.toContain("excluded");
    expect(fetched).not.toContain("seen");
  });

  test("unfiltered collection still rejects unpublished jobs", async () => {
    const recorded: OfferEvent[] = [];
    const fetchFn = async (input: string) => {
      const url = new URL(input);
      if (url.pathname.endsWith("/public/jobs")) {
        return jsonResponse({
          data: [makeWttjHit("draft", "full_time")],
          metadata: { page: 1, page_count: 1 },
        });
      }
      const payload = makeWttjDetail("draft", "full_time");
      payload.job.status = "draft";
      return jsonResponse(payload);
    };

    await collect(
      {} as DbPool,
      fetchFn,
      (e) => {
        recorded.push(e);
      },
      { baseUrl: "https://example.invalid", store: noopStore },
    );
    expect(recorded).toEqual([]);
  });

  test.skipIf(!getMysqlAdminUrl())("WTTJ run without results fails", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create("collector");
      const fetchFn = async () => jsonResponse({ data: [], metadata: { page: 1, page_count: 1 } });

      await expect(
        collect(pool, fetchFn, () => {}, { baseUrl: "https://example.invalid" }),
      ).rejects.toBeInstanceOf(SourceSilent);
    } finally {
      await ctx.cleanup();
    }
  });

  test("placeholder title is derived from slug or skipped", async () => {
    const recorded: OfferEvent[] = [];
    const fetchFn = async (input: string) => {
      const url = new URL(input);
      if (url.pathname.endsWith("/public/jobs")) {
        return jsonResponse({
          data: [makeWttjHit("derived"), makeWttjHit("unusable")],
          metadata: { page: 1, page_count: 1 },
        });
      }
      const identity = url.pathname.split("/").pop() ?? "";
      const payload = makeWttjDetail(identity);
      payload.job.name = " $1 ";
      payload.job.slug =
        identity === "derived"
          ? "network-security-implementation-specialist_milan_ND_wZVZKeo"
          : "_milan_ND_wZVZKeo";
      return jsonResponse(payload);
    };

    await collect(
      {} as DbPool,
      fetchFn,
      (e) => {
        recorded.push(e);
      },
      { baseUrl: "https://example.invalid", store: noopStore },
    );

    expect(recorded.map((e) => e.source_offer_id)).toEqual(["derived"]);
    expect(recorded[0]?.offer.title).toBe("Network security implementation specialist");
  });

  test("office without city is normalized as unknown city", () => {
    const payload = makeWttjDetail("no-city");
    payload.job.offices = [{ city: null as unknown as string, country_code: "FR" }];
    const job = DetailResponseSchema.parse(payload).job;
    const event = normalize(job, job.name);
    expect(event.offer.city).toBe("N/A");
    expect(event.offer.country).toBe("FR");
    expect(event.offer.fields[1]?.value).toBe("N/A (FR)");
  });
});
