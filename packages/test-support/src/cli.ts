import { afterEach } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { DbPool } from "@bovie/mysql-common";

/** A pool that CLI tests pass in place of MySQL; it only supports close(). */
export function stubPool(): DbPool {
  return {
    close: async () => {},
  } as unknown as DbPool;
}

/** A publisher that connects and closes; CLI tests replace collection itself. */
export function stubPublisher() {
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

/**
 * Restore process.env and the working directory after each test in the file.
 *
 * Call it once at the top of a CLI test file. Use the returned `makeTempDir()`
 * for a scratch directory that is deleted after the test.
 */
export function isolateProcess(): { makeTempDir(): string } {
  const savedEnv = { ...process.env };
  const savedCwd = process.cwd();
  const tempDirs: string[] = [];

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

  return {
    makeTempDir() {
      const dir = mkdtempSync(join(tmpdir(), "bovie-cli-test-"));
      tempDirs.push(dir);
      return dir;
    },
  };
}
