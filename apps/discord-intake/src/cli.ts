#!/usr/bin/env bun
import { configureLogging } from "@bovie/cli-common";
import { makePool } from "@bovie/mysql-common";
import { loadEnv } from "@bovie/mysql-common/env";
import { CONSUMER, connect, STREAM } from "@bovie/nats-client";
import { jetstream, jetstreamManager } from "@nats-io/jetstream";
import { Command } from "commander";
import { ensureConsumer, handle } from "./index.js";

export async function runCli(argv: string[]): Promise<void> {
  const program = new Command()
    .name("discord-intake")
    .description("Commit events and pending Discord deliveries before acknowledging NATS.")
    .option("--once", "Drain currently available messages and exit.", false)
    .action(async (options: { once: boolean }) => {
      configureLogging();
      const pool = makePool(loadEnv().databaseUrl);
      try {
        const nc = await connect();
        try {
          const jsm = await jetstreamManager(nc, { checkAPI: false });
          // With `--once`, a missing stream means there is nothing to drain.
          if (!(await ensureConsumer(jsm, { wait: !options.once }))) {
            return;
          }
          const js = jetstream(nc);
          const consumer = await js.consumers.get(STREAM, CONSUMER);

          while (true) {
            const messages = await consumer.fetch({ max_messages: 1, expires: 2000 });
            let received = 0;
            for await (const message of messages) {
              received += 1;
              if (!(await handle(pool, message)) && options.once) {
                throw new Error("Ingestion failed; message retained");
              }
            }
            if (received === 0 && options.once) {
              break;
            }
          }
        } finally {
          await nc.close();
        }
      } finally {
        await pool.close();
      }
    });

  await program.parseAsync(argv);
}

if (import.meta.main) {
  runCli(process.argv).catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exit(1);
  });
}
