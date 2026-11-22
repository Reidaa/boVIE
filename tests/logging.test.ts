import { describe, expect, test } from "bun:test";
import { configureLogging, logFailure, logger } from "@bovie/cli-common";

function captureStreams(fn: () => void): { stdout: string; stderr: string } {
  let stdout = "";
  let stderr = "";
  const origOut = process.stdout.write.bind(process.stdout);
  const origErr = process.stderr.write.bind(process.stderr);

  process.stdout.write = ((chunk: string | Uint8Array) => {
    stdout += typeof chunk === "string" ? chunk : Buffer.from(chunk).toString("utf8");
    return true;
  }) as typeof process.stdout.write;
  process.stderr.write = ((chunk: string | Uint8Array) => {
    stderr += typeof chunk === "string" ? chunk : Buffer.from(chunk).toString("utf8");
    return true;
  }) as typeof process.stderr.write;

  try {
    fn();
  } finally {
    process.stdout.write = origOut;
    process.stderr.write = origErr;
  }
  return { stdout, stderr };
}

describe("cli-common logging", () => {
  test("errors go to stderr and the rest to stdout", () => {
    const captured = captureStreams(() => {
      configureLogging({ debug: true });
      logger.debug("debug message");
      logger.info("info message");
      logger.error("error message");
    });

    expect(captured.stdout).toContain("debug message");
    expect(captured.stdout).toContain("info message");
    expect(captured.stdout).not.toContain("error message");
    expect(captured.stderr).toContain("error message");
    expect(captured.stderr).not.toContain("info message");
  });

  test("debug messages are hidden by default", () => {
    const captured = captureStreams(() => {
      configureLogging();
      logger.debug("debug message");
    });
    expect(captured.stdout).not.toContain("debug message");
  });

  test("logFailure omits secret exception messages", () => {
    const captured = captureStreams(() => {
      configureLogging();
      logFailure(new Error("https://discord.com/api/webhooks/secret-token"), "Discord delivery");
    });
    expect(captured.stderr).toContain("Discord delivery failed (Error).");
    expect(captured.stderr).not.toContain("secret-token");
  });
});
