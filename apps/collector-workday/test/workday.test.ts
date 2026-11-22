import { describe, expect, test } from "bun:test";
import { upgrade as upgradeCollector } from "@bovie/collector-store";
import type { DbPool, RowDataPacket } from "@bovie/mysql-common";
import type { OfferEvent } from "@bovie/offer-events";
import { createTestDbContext, getMysqlAdminUrl, jsonResponse } from "@bovie/test-support";
import {
  type Board,
  CollectionFailed,
  collect,
  type FetchLike,
  JobDetailSchema,
  loadBoards,
  normalize,
  parseBoard,
  type WorkdayCollectOptions,
} from "../src/index.js";

const API = "/wday/cxs/example/Careers";

function makeBoard(overrides: Record<string, unknown> = {}): Board {
  return parseBoard({
    url: "https://example.wd3.myworkdayjobs.com/en-US/Careers",
    company: "Example",
    ...overrides,
  });
}

function makePosting(identity: string) {
  return {
    title: "Engineer",
    externalPath: `/job/Paris/${identity}`,
    locationsText: "Paris",
    postedOn: "Posted Today",
  };
}

function makeDetail(identity: string, info: Record<string, unknown> = {}) {
  return {
    jobPostingInfo: {
      id: "0123456789abcdef",
      title: " Data Engineer ",
      location: "Paris",
      additionalLocations: ["Lyon"],
      startDate: "2026-10-27",
      endDate: "2026-11-05",
      timeType: "Full time",
      jobReqId: "R1",
      jobPostingId: identity,
      posted: true,
      jobRequisitionLocation: {
        descriptor: "Paris",
        country: { descriptor: "France", alpha2Code: "FR" },
      },
      ...info,
    },
    hiringOrganization: { name: "(1675) Internal entity", url: "" },
  };
}

function makePages(
  pageList: Array<Array<ReturnType<typeof makePosting>>>,
  total?: number,
): FetchLike {
  const size = pageList[0]?.length ?? 0;
  return async (input, init) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body)) as { offset: number };
      const index = size > 0 ? Math.floor(body.offset / size) : 0;
      const page = pageList[index] ?? pageList[0] ?? [];
      const count = total ?? pageList.reduce((acc, p) => acc + p.length, 0);
      return jsonResponse({
        total: body.offset === 0 ? count : 0,
        jobPostings: page,
      });
    }
    const id = new URL(input).pathname.split("/").pop() ?? "";
    return jsonResponse(makeDetail(id));
  };
}

const noopStore = {
  seen: async () => false,
  recordPage: async () => {},
  requireRecentResults: async () => {},
};

async function runWorkday(
  pool: DbPool,
  fetchFn: FetchLike,
  boards: readonly Board[],
  options: WorkdayCollectOptions = {},
): Promise<OfferEvent[]> {
  const published: OfferEvent[] = [];
  await collect(
    pool,
    fetchFn,
    (e) => {
      published.push(e);
    },
    boards,
    { delay: 0, ...options },
  );
  return published;
}

describe("workday collector", () => {
  test("board reads tenant, host, and site from its public URL", () => {
    const example = makeBoard();
    expect(example.apiUrl).toBe(`https://example.wd3.myworkdayjobs.com${API}`);
    expect(example.tenant).toBe("example");
    expect(example.site).toBe("Careers");
    expect(() => makeBoard({ url: "https://example.com/Careers" })).toThrow();
    expect(() => makeBoard({ url: "https://example.wd3.myworkdayjobs.com/" })).toThrow();
  });

  test("board accepts snake_case filters like the Python config", () => {
    const board = makeBoard({ search_text: "data", applied_facets: { a: ["1"] } });
    expect(board.searchText).toBe("data");
    expect(board.appliedFacets).toEqual({ a: ["1"] });
    expect(() => makeBoard({ search_text: "a", searchText: "b" })).toThrow();
  });

  for (const text of ["", "  ", "[]"]) {
    test(`boards are required (${JSON.stringify(text)})`, () => {
      expect(() => loadBoards(text)).toThrow(/WORKDAY_BOARDS/);
    });
  }

  test("detail normalization", () => {
    const job = JobDetailSchema.parse(makeDetail("Data-Engineer_R1").jobPostingInfo);
    const event = normalize(makeBoard(), "/job/Paris/Data-Engineer_R1", job);
    expect(event.source).toBe("workday");
    expect(event.source_offer_id).toBe("example/Careers/Data-Engineer_R1");
    expect(event.offer.title).toBe("Data Engineer");
    expect(event.offer.organization).toBe("Example");
    expect(event.offer.country).toBe("FR");
    expect(event.offer.city).toBe("Paris");
    expect(event.offer.url).toBe(
      "https://example.wd3.myworkdayjobs.com/Careers/job/Paris/Data-Engineer_R1",
    );
    expect(Object.fromEntries(event.offer.fields.map((f) => [f.name, f.value]))).toEqual({
      Entreprise: "Example",
      Lieu: "Paris, Lyon",
      "Publié le": "2026-10-27",
      Contrat: "Full time",
      "Date limite": "2026-11-05",
      Référence: "R1",
    });
  });

  test("detail normalization without optional fields", () => {
    const job = JobDetailSchema.parse({
      title: "Engineer",
      jobPostingId: "Engineer_R2",
      posted: true,
    });
    const event = normalize(makeBoard(), "/job/x/Engineer_R2", job);
    expect(event.offer.country).toBe("N/A");
    expect(event.offer.city).toBe("N/A");
    expect(event.offer.fields.map((f) => f.name)).toEqual(["Entreprise", "Lieu"]);
  });

  test.skipIf(!getMysqlAdminUrl())("pagination records offers and skips known ones", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      const requests: Array<{ method: string; url: string; body?: string }> = [];
      const serve = makePages([
        Array.from({ length: 20 }, (_, i) => makePosting(`job-${i}`)),
        [makePosting("job-20"), makePosting("job-21")],
      ]);

      const handler: FetchLike = async (input, init) => {
        requests.push({
          method: init?.method ?? "GET",
          url: input,
          body: init?.body ? String(init.body) : undefined,
        });
        return serve(input, init);
      };

      const first = await runWorkday(pool, handler, [makeBoard()], { limit: 40 });
      expect(first.map((e) => e.source_offer_id.split("/").pop())).toEqual(
        Array.from({ length: 22 }, (_, i) => `job-${i}`),
      );

      const bodies = requests.filter((r) => r.method === "POST").map((r) => JSON.parse(r.body!));
      expect(bodies).toEqual([
        { limit: 20, offset: 0, searchText: "", appliedFacets: {} },
        { limit: 20, offset: 20, searchText: "", appliedFacets: {} },
      ]);
      expect(
        requests.every((r) => r.url.startsWith(`https://example.wd3.myworkdayjobs.com${API}/`)),
      ).toBe(true);

      requests.length = 0;
      expect(await runWorkday(pool, handler, [makeBoard()], { limit: 40 })).toEqual([]);
      expect(requests.every((r) => r.method === "POST")).toBe(true);

      const [[countRow]] = await pool.query<RowDataPacket[]>(
        "SELECT COUNT(*) AS count FROM offers",
      );
      expect(Number(countRow?.count)).toBe(22);
    } finally {
      await ctx.cleanup();
    }
  });

  test("pagination stops at limit and total", async () => {
    const offsets: number[] = [];
    const full = Array.from({ length: 20 }, (_, i) => makePosting(`job-${i}`));
    const serve = makePages([full, full, full], 40);

    const handler: FetchLike = async (input, init) => {
      if (init?.method === "POST") {
        offsets.push((JSON.parse(String(init.body)) as { offset: number }).offset);
      }
      return serve(input, init);
    };

    await runWorkday({} as DbPool, handler, [makeBoard()], { limit: 100, store: noopStore });
    expect(offsets).toEqual([0, 20]);

    offsets.length = 0;
    const limited = await runWorkday({} as DbPool, handler, [makeBoard()], {
      limit: 25,
      store: noopStore,
    });
    expect(limited.length).toBe(25);
    expect(offsets).toEqual([0, 20]);
  });

  test("filters are sent in the search body", async () => {
    const bodies: Array<Record<string, unknown>> = [];
    const serve = makePages([[makePosting("job")]]);

    const handler: FetchLike = async (input, init) => {
      if (init?.method === "POST") {
        bodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      }
      return serve(input, init);
    };

    const facets = { locationCountry: ["54c5b6971ffb4bf0b116fe7651ec789a"] };
    const filtered = makeBoard({ searchText: "data", appliedFacets: facets });
    await runWorkday({} as DbPool, handler, [filtered], { store: noopStore });
    expect(bodies[0]?.searchText).toBe("data");
    expect(bodies[0]?.appliedFacets).toEqual(facets);
  });

  test.skipIf(!getMysqlAdminUrl())(
    "failed page keeps earlier pages and fails the run",
    async () => {
      const ctx = await createTestDbContext();
      try {
        const pool = await ctx.create(upgradeCollector);
        const serve = makePages([
          Array.from({ length: 20 }, (_, i) => makePosting(`job-${i}`)),
          [makePosting("job-20")],
        ]);
        const published: OfferEvent[] = [];

        const handler: FetchLike = async (input, init) => {
          if (
            init?.method === "POST" &&
            (JSON.parse(String(init.body)) as { offset: number }).offset === 20
          ) {
            return new Response(null, { status: 503 });
          }
          return serve(input, init);
        };

        await expect(
          collect(
            pool,
            handler,
            (e) => {
              published.push(e);
            },
            [makeBoard()],
            { delay: 0 },
          ),
        ).rejects.toBeInstanceOf(CollectionFailed);

        expect(published.length).toBe(20);
        const [[offers]] = await pool.query<RowDataPacket[]>(
          "SELECT COUNT(*) AS count FROM offers",
        );
        const [[cp]] = await pool.query<RowDataPacket[]>("SELECT `offset` FROM checkpoints");
        expect(Number(offers?.count)).toBe(20);
        expect(Number(cp?.offset)).toBe(0);
      } finally {
        await ctx.cleanup();
      }
    },
  );

  test.skipIf(!getMysqlAdminUrl())("failed detail does not commit page", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      const serve = makePages([[makePosting("first"), makePosting("second")]]);

      const handler: FetchLike = async (input, init) => {
        if (new URL(input).pathname.endsWith("/second")) {
          return new Response(null, { status: 503 });
        }
        return serve(input, init);
      };

      await expect(runWorkday(pool, handler, [makeBoard()])).rejects.toBeInstanceOf(
        CollectionFailed,
      );
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

  const brokenResponses: Array<[string, () => Promise<Response>]> = [
    ["HTTP error", async () => new Response(null, { status: 422 })],
    [
      "connection error",
      async () => {
        // Bun's fetch rejects with TypeError when the connection is refused.
        throw new TypeError("Unable to connect");
      },
    ],
    [
      "body read error",
      async () =>
        new Response(
          new ReadableStream({
            start(controller) {
              controller.error(new TypeError("Connection reset"));
            },
          }),
        ),
    ],
  ];
  test.each(brokenResponses)("a failed board does not stop the others (%s)", async (_, fail) => {
    const serve = makePages([[makePosting("job")]]);
    const handler: FetchLike = async (input, init) => {
      if (new URL(input).hostname.startsWith("broken.")) {
        return fail();
      }
      return serve(input, init);
    };

    const broken = makeBoard({ url: "https://broken.wd1.myworkdayjobs.com/Careers" });
    const published: OfferEvent[] = [];

    await expect(
      collect(
        {} as DbPool,
        handler,
        (e) => {
          published.push(e);
        },
        [broken, makeBoard()],
        { delay: 0, store: noopStore },
      ),
    ).rejects.toThrow(/broken\/Careers/);

    expect(published.map((e) => e.source_offer_id)).toEqual(["example/Careers/job"]);
  });

  test("removed and unposted jobs are skipped", async () => {
    const serve = makePages([[makePosting("gone"), makePosting("draft"), makePosting("open")]]);
    const handler: FetchLike = async (input, init) => {
      const path = new URL(input).pathname;
      if (path.endsWith("/gone")) {
        return jsonResponse({ errorCode: "S21" }, 404);
      }
      if (path.endsWith("/draft")) {
        return jsonResponse(makeDetail("draft", { posted: false }));
      }
      return serve(input, init);
    };

    const published = await runWorkday({} as DbPool, handler, [makeBoard()], { store: noopStore });
    expect(published.map((e) => e.source_offer_id)).toEqual(["example/Careers/open"]);
  });

  test("detail identity must match the posting", async () => {
    const serve = makePages([[makePosting("listed")]]);
    const handler: FetchLike = async (input, init) => {
      if ((init?.method ?? "GET") === "GET") {
        return jsonResponse(makeDetail("other"));
      }
      return serve(input, init);
    };

    await expect(
      runWorkday({} as DbPool, handler, [makeBoard()], { store: noopStore }),
    ).rejects.toBeInstanceOf(CollectionFailed);
  });

  test.skipIf(!getMysqlAdminUrl())("board without results fails", async () => {
    const ctx = await createTestDbContext();
    try {
      const pool = await ctx.create(upgradeCollector);
      await expect(runWorkday(pool, makePages([[]]), [makeBoard()])).rejects.toThrow(
        /example\/Careers/,
      );
    } finally {
      await ctx.cleanup();
    }
  });

  test("a broker failure stops the run immediately", async () => {
    const hosts: string[] = [];
    const serve = makePages([[makePosting("job")]]);
    const handler: FetchLike = async (input, init) => {
      hosts.push(new URL(input).hostname);
      return serve(input, init);
    };

    const second = makeBoard({ url: "https://second.wd1.myworkdayjobs.com/Careers" });
    await expect(
      collect(
        {} as DbPool,
        handler,
        () => {
          throw new Error("broker down");
        },
        [makeBoard(), second],
        { delay: 0, store: noopStore },
      ),
    ).rejects.toThrow("broker down");

    expect(hosts).not.toContain("second.wd1.myworkdayjobs.com");
  });
});
