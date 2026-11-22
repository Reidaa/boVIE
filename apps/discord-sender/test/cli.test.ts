import { describe, expect, test } from "bun:test";
import { isolateProcess } from "@bovie/test-support";
import { runCli as runSenderCli } from "../src/cli.js";

const { makeTempDir } = isolateProcess();

describe("discord-sender CLI", () => {
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
