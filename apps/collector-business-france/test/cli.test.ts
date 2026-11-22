import { describe, expect, test } from "bun:test";
import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { isolateProcess, stubPool, stubPublisher } from "@bovie/test-support";
import { parse as parseDotenv } from "dotenv";
import { runCli as runBfCli } from "../src/cli.js";
import type { SearchParameters } from "../src/index.js";

const ROOT = resolve(import.meta.dirname, "../../..");
const { makeTempDir } = isolateProcess();

describe("collector-business-france CLI", () => {
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
});
