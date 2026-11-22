import { describe, expect, test } from "bun:test";
import { MAX_SILENCE_MS, SourceSilent, upgrade as upgradeCollector } from "@bovie/collector-store";
import { formatUtcDateTime, type RowDataPacket } from "@bovie/mysql-common";
import type { OfferEvent } from "@bovie/offer-events";
import { createTestDbContext, getMysqlAdminUrl } from "@bovie/test-support";
import { createSearchParameters, type Job, normalize, task } from "../src/index.js";

function makeBfJob(identity: number, overrides: Partial<Job> = {}): Job {
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

describe("business france collection", () => {
  test.skipIf(!getMysqlAdminUrl())("interrupted collection replays without skipping", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      const searchId = async (params: { skip: number }) =>
        ({ 0: [1, 2], 2: [3] })[params.skip] ?? [];

      const published: OfferEvent[] = [];
      await expect(
        task(
          createSearchParameters({ limit: 3 }),
          pool,
          (e) => {
            published.push(e);
          },
          {
            pageSize: 2,
            deps: {
              searchId,
              getFromId: async (id) => {
                if (id === 3) {
                  throw new Error("upstream failure");
                }
                return makeBfJob(id);
              },
            },
          },
        ),
      ).rejects.toThrow("upstream failure");
      expect(published.map((e) => e.source_offer_id)).toEqual(["1", "2"]);

      const deps = { searchId, getFromId: async (id: number) => makeBfJob(id) };
      await task(
        createSearchParameters({ limit: 3 }),
        pool,
        (e) => {
          published.push(e);
        },
        { pageSize: 2, deps },
      );
      await task(
        createSearchParameters({ limit: 3 }),
        pool,
        (e) => {
          published.push(e);
        },
        { pageSize: 2, deps },
      );

      expect(published.map((e) => e.source_offer_id)).toEqual(["1", "2", "3"]);
      const [[offers]] = await pool.query<RowDataPacket[]>("SELECT COUNT(*) AS count FROM offers");
      expect(Number(offers?.count)).toBe(3);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())("failed publish leaves page unrecorded", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      const deps = {
        searchId: async () => [1, 2],
        getFromId: async (id: number) => makeBfJob(id),
      };
      const published: OfferEvent[] = [];

      await expect(
        task(
          createSearchParameters({ limit: 2 }),
          pool,
          (e) => {
            published.push(e);
            if (published.length === 2) {
              throw new Error("Lost publish acknowledgment");
            }
          },
          { deps },
        ),
      ).rejects.toThrow("Lost publish acknowledgment");

      const [[offersBefore]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM offers",
      );
      const [[cpBefore]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM checkpoints",
      );
      expect(Number(offersBefore?.count)).toBe(0);
      expect(Number(cpBefore?.count)).toBe(0);

      await task(
        createSearchParameters({ limit: 2 }),
        pool,
        (e) => {
          published.push(e);
        },
        { deps },
      );
      expect(published.slice(2).map((e) => e.event_id)).toEqual(
        published.slice(0, 2).map((e) => e.event_id),
      );
      const [[offersAfter]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM offers",
      );
      expect(Number(offersAfter?.count)).toBe(2);
    } finally {
      await ctx.cleanup();
    }
  });

  test.skipIf(!getMysqlAdminUrl())(
    "offer removed before its details are read is skipped",
    async () => {
      const ctx = await createTestDbContext();
      try {
        const pool = await ctx.create(upgradeCollector);
        const published: OfferEvent[] = [];
        await task(
          createSearchParameters({ limit: 2 }),
          pool,
          (e) => {
            published.push(e);
          },
          {
            deps: {
              searchId: async () => [1, 2],
              getFromId: async (id) => (id === 1 ? null : makeBfJob(id)),
            },
          },
        );
        expect(published.map((e) => e.source_offer_id)).toEqual(["2"]);
      } finally {
        await ctx.cleanup();
      }
    },
  );

  test("preserves display fields", () => {
    const event = normalize(makeBfJob(1));
    expect(event.source_offer_id).toBe("1");
    expect(event.offer.country).toBe("Canada");
    expect(event.offer.fields.length).toBe(14);
  });

  test("long display values are truncated to 1024", () => {
    const event = normalize(makeBfJob(1, { contactEmail: "x".repeat(2000) }));
    expect(Math.max(...event.offer.fields.map((f) => f.value.length))).toBe(1024);
  });

  test.skipIf(!getMysqlAdminUrl())(
    "source without results for too long fails the run",
    async () => {
      const ctx = await createTestDbContext();
      try {
        const pool = await ctx.create(upgradeCollector);
        let results = [1];
        const deps = {
          searchId: async () => [...results],
          getFromId: async (id: number) => makeBfJob(id),
        };
        await task(createSearchParameters({ limit: 1 }), pool, () => {}, { deps });
        results = [];
        // A short gap is normal; the run succeeds.
        await task(createSearchParameters({ limit: 1 }), pool, () => {}, { deps });
        await pool.execute("UPDATE checkpoints SET results_seen_at = ?", [
          formatUtcDateTime(new Date(Date.now() - MAX_SILENCE_MS - 60_000)),
        ]);
        await expect(
          task(createSearchParameters({ limit: 1 }), pool, () => {}, { deps }),
        ).rejects.toBeInstanceOf(SourceSilent);
      } finally {
        await ctx.cleanup();
      }
    },
  );

  test.skipIf(!getMysqlAdminUrl())("first run without results fails", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      await expect(
        task(createSearchParameters({ limit: 1 }), pool, () => {}, {
          deps: {
            searchId: async () => [],
            getFromId: async () => null,
          },
        }),
      ).rejects.toBeInstanceOf(SourceSilent);
    } finally {
      await ctx.cleanup();
    }
  });
});
