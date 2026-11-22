#!/usr/bin/env bun
import { configureLogging, logFailure, logger } from "@bovie/cli-common";
import { makePool } from "@bovie/mysql-common";
import { loadEnv } from "@bovie/mysql-common/env";
import { Command } from "commander";
import { deliverOne } from "./index.js";

export interface SenderCliRuntime {
  makePool?: typeof makePool;
  deliver?: typeof deliverOne;
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

export async function runCli(argv: string[], runtime: SenderCliRuntime = {}): Promise<void> {
  const program = new Command()
    .name("discord-sender")
    .description("Send queued Discord messages using only Discord database credentials.")
    .option("--once", "Drain currently available deliveries and exit.", false)
    .action(async (options: { once: boolean }) => {
      configureLogging();
      const webhook = process.env.DISCORD_WEBHOOK_URL;
      if (!webhook) {
        // PR environments have no webhook: Railway does not copy sealed variables.
        // Messages stay queued, and exiting cleanly stops Railway from restarting.
        logger.warning("DISCORD_WEBHOOK_URL is not set; Discord delivery is off");
        return;
      }

      const poolFactory = runtime.makePool ?? makePool;
      const deliver = runtime.deliver ?? deliverOne;
      const pool = poolFactory(loadEnv().databaseUrl);

      try {
        while (true) {
          let processed: boolean;
          try {
            processed = await deliver(pool, (input, init) => fetch(input, init), webhook);
          } catch (error) {
            logFailure(error, "Discord delivery");
            if (options.once) {
              throw new Error("Delivery failed; pending work retained");
            }
            processed = false;
          }
          if (!processed) {
            if (options.once) {
              break;
            }
            await sleep(1000);
          }
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
