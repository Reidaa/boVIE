import { describe, expect, test } from "bun:test";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { DbPool } from "@bovie/mysql-common";
import { isolateProcess, stubPool, stubPublisher } from "@bovie/test-support";
import { runCli as runWttjCli } from "../src/cli.js";
import type { CollectOptions } from "../src/index.js";

const { makeTempDir } = isolateProcess();

describe("collector-wttj CLI", () => {
  test("WTTJ CLI defaults and optional contract filters", async () => {
    const dir = makeTempDir();
    process.chdir(dir);
    for (const key of ["WTTJ_QUERY", "WTTJ_CONTRACTS", "WTTJ_LIMIT", "WTTJ_MAX_PAGES"]) {
      delete process.env[key];
    }
    process.env.DATABASE_URL = "mysql://u:p@localhost/source";

    const observed: CollectOptions[] = [];
    const runtime = {
      makePool: () => stubPool(),
      createPublisher: stubPublisher,
      runCollect: async (_pool: DbPool, _fetch: unknown, _pub: unknown, opts: CollectOptions) => {
        observed.push(opts);
      },
    };

    await runWttjCli(["bun", "collector-wttj"], runtime);
    expect(observed[observed.length - 1]?.query).toBe("");
    expect(observed[observed.length - 1]?.contracts).toEqual([]);

    writeFileSync(join(dir, ".env"), "WTTJ_QUERY=engineer\nWTTJ_CONTRACTS=full_time internship\n");
    await runWttjCli(["bun", "collector-wttj"], runtime);
    expect(observed[observed.length - 1]?.query).toBe("engineer");
    expect(observed[observed.length - 1]?.contracts).toEqual(["full_time", "internship"]);

    await runWttjCli(
      ["bun", "collector-wttj", "--contract", "FREELANCE", "--country", "ca"],
      runtime,
    );
    expect(observed[observed.length - 1]?.contracts).toEqual(["freelance"]);
    expect(observed[observed.length - 1]?.countries).toEqual(["CA"]);
  });
});
