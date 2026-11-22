import { afterEach, describe, expect, test } from "bun:test";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import type { DbPool } from "@bovie/mysql-common";
import { parse as parseDotenv } from "dotenv";
import { runCli as runBfCli } from "../apps/collector-business-france/dist/cli.js";
import type { SearchParameters } from "../apps/collector-business-france/dist/index.js";
import { CliUsageError, runCli as runWorkdayCli } from "../apps/collector-workday/dist/cli.js";
import type { Board, WorkdayCollectOptions } from "../apps/collector-workday/dist/index.js";
import { runCli as runWttjCli } from "../apps/collector-wttj/dist/cli.js";
import type { CollectOptions } from "../apps/collector-wttj/dist/index.js";
import { runCli as runSenderCli } from "../apps/discord-sender/dist/cli.js";

const ROOT = resolve(import.meta.dirname, "..");

function stubPool(): DbPool {
  return {
    close: async () => {},
  } as unknown as DbPool;
}

function stubPublisher() {
  return {
    async connect() {
      return this;
    },
    async publish() {
      throw new Error("CLI tests replace collection");
    },
    async close() {},
  };
}

const savedEnv = { ...process.env };
const savedCwd = process.cwd();
const tempDirs: string[] = [];

function makeTempDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "bovie-cli-test-"));
  tempDirs.push(dir);
  return dir;
}

afterEach(() => {
  process.chdir(savedCwd);
  for (const key of Object.keys(process.env)) {
    if (!(key in savedEnv)) {
      delete process.env[key];
    }
  }
  for (const [key, value] of Object.entries(savedEnv)) {
    process.env[key] = value;
  }
  while (tempDirs.length > 0) {
    const dir = tempDirs.pop();
    if (dir) {
      rmSync(dir, { recursive: true, force: true });
    }
  }
});

describe("CLI entrypoints", () => {
  test("Business France CLI loads .env before resolving options", async () => {
    const dir = makeTempDir();
    process.chdir(dir);
    writeFileSync(
      join(dir, ".env"),
      "BUSINESS_FRANCE_LIMIT=7\nDATABASE_URL=mysql://u:p@localhost/source\n",
    );
    delete process.env.BUSINESS_FRANCE_LIMIT;
    delete process.env.DATABASE_URL;

    const observed: number[] = [];
    await runBfCli(["bun", "collector-business-france"], {
      makePool: () => stubPool(),
      createPublisher: stubPublisher,
      runTask: async (params) => {
        observed.push(params.limit);
      },
    });
    expect(observed).toEqual([7]);
  });

  test(".env.example is accepted by Business France CLI", async () => {
    const values = parseDotenv(readFileSync(join(ROOT, ".env.example"), "utf8"));
    for (const [key, value] of Object.entries(values)) {
      process.env[key] = value;
    }

    const observed: SearchParameters[] = [];
    await runBfCli(["bun", "collector-business-france"], {
      makePool: () => stubPool(),
      createPublisher: stubPublisher,
      runTask: async (params) => {
        observed.push(params);
      },
    });

    expect(observed[0]?.limit).toBe(25);
    expect(observed[0]?.countriesIds.length).toBeGreaterThan(0);
  });

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

  const BOARD = '{"url": "https://example.wd1.myworkdayjobs.com/Careers", "company": "Example"';

  test("Workday CLI reads boards from environment and flags", async () => {
    const dir = makeTempDir();
    process.chdir(dir);
    delete process.env.WORKDAY_BOARDS;
    delete process.env.WORKDAY_LIMIT;
    process.env.DATABASE_URL = "mysql://u:p@localhost/source";

    const observed: Array<{ boards: readonly Board[]; opts: WorkdayCollectOptions }> = [];
    const runtime = {
      makePool: () => stubPool(),
      createPublisher: stubPublisher,
      runCollect: async (
        _pool: DbPool,
        _fetch: unknown,
        _pub: unknown,
        boards: readonly Board[],
        opts: WorkdayCollectOptions,
      ) => {
        observed.push({ boards, opts });
      },
    };

    writeFileSync(
      join(dir, ".env"),
      `WORKDAY_LIMIT=5\nWORKDAY_BOARDS='[${BOARD}, "searchText": "data"}]'\n`,
    );
    await runWorkdayCli(["bun", "collector-workday"], runtime);
    expect(observed[observed.length - 1]?.boards[0]?.name).toBe("example/Careers");
    expect(observed[observed.length - 1]?.boards[0]?.searchText).toBe("data");
    expect(observed[observed.length - 1]?.opts.limit).toBe(5);

    await runWorkdayCli(["bun", "collector-workday", "--boards", `[${BOARD}}]`], runtime);
    expect(observed[observed.length - 1]?.boards[0]?.searchText).toBe("");

    await expect(
      runWorkdayCli(["bun", "collector-workday", "--boards", '[{"url": "x"}]'], runtime),
    ).rejects.toMatchObject({ exitCode: 2 });
  });

  for (const value of [undefined, "", "[]"]) {
    test(`Workday CLI without boards fails before connecting (${String(value)})`, async () => {
      const dir = makeTempDir();
      process.chdir(dir);
      delete process.env.WORKDAY_BOARDS;
      if (value !== undefined) {
        process.env.WORKDAY_BOARDS = value;
      }
      process.env.DATABASE_URL = "mysql://u:p@localhost/source";

      const refuse = () => {
        throw new Error("connected without boards");
      };

      try {
        await runWorkdayCli(["bun", "collector-workday"], {
          makePool: refuse,
          createPublisher: refuse,
        });
        throw new Error("Expected CliUsageError");
      } catch (error) {
        expect(error).toBeInstanceOf(CliUsageError);
        expect((error as CliUsageError).exitCode).toBe(2);
        expect((error as Error).message).toContain("WORKDAY_BOARDS");
      }
    });
  }

  test("Business France failure is logged on stderr", async () => {
    process.env.DATABASE_URL = "mysql://u:p@localhost/source";
    let stdout = "";
    let stderr = "";
    const origOut = process.stdout.write.bind(process.stdout);
    const origErr = process.stderr.write.bind(process.stderr);
    process.stdout.write = ((chunk: string | Uint8Array) => {
      stdout += String(chunk);
      return true;
    }) as typeof process.stdout.write;
    process.stderr.write = ((chunk: string | Uint8Array) => {
      stderr += String(chunk);
      return true;
    }) as typeof process.stderr.write;

    try {
      await expect(
        runBfCli(["bun", "collector-business-france"], {
          makePool: () => stubPool(),
          createPublisher: stubPublisher,
          runTask: async () => {
            throw new Error("source down");
          },
        }),
      ).rejects.toThrow(/Business France collection failed/);
    } finally {
      process.stdout.write = origOut;
      process.stderr.write = origErr;
    }

    expect(stdout).toContain("| INFO     |");
    expect(stdout).toContain("Starting");
    expect(stderr).toContain("| ERROR    |");
    expect(stderr).toContain("source down");
    expect(stdout).not.toContain("| ERROR    |");
  });

  test("discord-sender without webhook turns delivery off cleanly", async () => {
    const dir = makeTempDir();
    process.chdir(dir);
    delete process.env.DISCORD_WEBHOOK_URL;
    let stdout = "";
    const origOut = process.stdout.write.bind(process.stdout);
    process.stdout.write = ((chunk: string | Uint8Array) => {
      stdout += String(chunk);
      return true;
    }) as typeof process.stdout.write;

    try {
      await runSenderCli(["bun", "discord-sender"], {
        makePool: () => {
          throw new Error("should not connect without webhook");
        },
      });
    } finally {
      process.stdout.write = origOut;
    }

    expect(stdout).toContain("Discord delivery is off");
  });
});
