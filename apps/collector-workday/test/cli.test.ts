import { describe, expect, test } from "bun:test";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { DbPool } from "@bovie/mysql-common";
import { isolateProcess, stubPool, stubPublisher } from "@bovie/test-support";
import { CliUsageError, runCli as runWorkdayCli } from "../src/cli.js";
import type { Board, WorkdayCollectOptions } from "../src/index.js";

const { makeTempDir } = isolateProcess();

describe("collector-workday CLI", () => {
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
});
