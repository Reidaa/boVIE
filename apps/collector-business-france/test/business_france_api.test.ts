import { afterEach, describe, expect, test } from "bun:test";
import { jsonResponse } from "@bovie/test-support";
import {
  BusinessFranceClient,
  createSearchParameters,
  HttpStatusError,
  PUBLIC_OFFERS_URL,
} from "../src/index.js";

function publicSite(...keys: string[]) {
  let index = 0;
  return (): Response => {
    const key = keys[index++];
    return new Response(`<script>config:{API_KEY:"${key}"}</script>`, { status: 200 });
  };
}

const originalApiKey = process.env.BUSINESS_FRANCE_API_KEY;

afterEach(() => {
  if (originalApiKey === undefined) {
    delete process.env.BUSINESS_FRANCE_API_KEY;
  } else {
    process.env.BUSINESS_FRANCE_API_KEY = originalApiKey;
  }
});

describe("business france API client", () => {
  test("search uses public site key and API field names", async () => {
    delete process.env.BUSINESS_FRANCE_API_KEY;
    const page = publicSite("public\\/key");

    const client = new BusinessFranceClient({
      fetchFn: async (input, init) => {
        if (input === PUBLIC_OFFERS_URL) {
          return page();
        }
        expect(input.endsWith("/search")).toBe(true);
        const headers = new Headers(init?.headers);
        expect(headers.get("X-API-KEY")).toBe("public/key");
        const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
        expect(body.geographicZones).toEqual(["5"]);
        expect("gerographicZones" in body).toBe(false);
        return jsonResponse({ result: [{ id: 42 }] });
      },
    });

    expect(await client.searchId(createSearchParameters({ geographicZones: ["5"] }))).toEqual([42]);
  });

  test("rotated key is fetched again and the request retried", async () => {
    delete process.env.BUSINESS_FRANCE_API_KEY;
    const page = publicSite("old", "new");
    const sent: Array<[string | null, Record<string, unknown>]> = [];

    const client = new BusinessFranceClient({
      fetchFn: async (input, init) => {
        if (input === PUBLIC_OFFERS_URL) {
          return page();
        }
        const key = new Headers(init?.headers).get("X-API-KEY");
        const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
        sent.push([key, body]);
        if (key === "old") {
          return new Response(null, { status: 401 });
        }
        return jsonResponse({ result: [{ id: 7 }] });
      },
    });

    expect(await client.searchId(createSearchParameters({ limit: 3 }))).toEqual([7]);
    expect(sent.map(([key]) => key)).toEqual(["old", "new"]);
    expect(sent[0]?.[1]).toEqual(sent[1]?.[1]);
    expect(sent[1]?.[1].limit).toBe(3);
  });

  test("configured key is used without reading the site", async () => {
    process.env.BUSINESS_FRANCE_API_KEY = "configured";

    const client = new BusinessFranceClient({
      fetchFn: async (input, init) => {
        expect(input).not.toBe(PUBLIC_OFFERS_URL);
        expect(new Headers(init?.headers).get("X-API-KEY")).toBe("configured");
        return jsonResponse({ id: 1 });
      },
    });

    const response = await client.request("GET", "/details/1");
    expect(await response.json()).toEqual({ id: 1 });
  });

  test("stale configured key is replaced once per run", async () => {
    process.env.BUSINESS_FRANCE_API_KEY = "stale";
    const page = publicSite("public");
    const sent: Array<string | null> = [];

    const client = new BusinessFranceClient({
      fetchFn: async (input, init) => {
        if (input === PUBLIC_OFFERS_URL) {
          return page();
        }
        const key = new Headers(init?.headers).get("X-API-KEY");
        sent.push(key);
        if (key === "stale") {
          return new Response(null, { status: 401 });
        }
        return jsonResponse({ id: 1 });
      },
    });

    await client.request("GET", "/details/1");
    await client.request("GET", "/details/2");
    expect(sent).toEqual(["stale", "public", "public"]);
  });

  test("a second unauthorized response fails the run", async () => {
    delete process.env.BUSINESS_FRANCE_API_KEY;
    const page = publicSite("old", "still-wrong");

    const client = new BusinessFranceClient({
      fetchFn: async (input) => {
        if (input === PUBLIC_OFFERS_URL) {
          return page();
        }
        return new Response(null, { status: 401 });
      },
    });

    await expect(client.searchId(createSearchParameters())).rejects.toBeInstanceOf(HttpStatusError);
  });

  for (const status of [404, 410]) {
    test(`offer removed before details are read returns null (${status})`, async () => {
      const client = new BusinessFranceClient({
        fetchFn: async () => new Response(null, { status }),
      });
      client.apiKey = "key";
      expect(await client.getFromId(9)).toBeNull();
    });
  }

  test("other detail failures fail the run", async () => {
    const client = new BusinessFranceClient({
      fetchFn: async () => new Response(null, { status: 503 }),
    });
    client.apiKey = "key";
    await expect(client.getFromId(9)).rejects.toBeInstanceOf(HttpStatusError);
  });
});
