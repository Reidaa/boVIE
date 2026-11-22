#!/usr/bin/env bun
import { makePool } from "@bovie/mysql-common";
import { loadEnv } from "@bovie/mysql-common/env";
import { Command, InvalidArgumentError } from "commander";
import { upgrade } from "./index.js";

function parseNonNegativeNumber(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new InvalidArgumentError("Must be a non-negative number");
  }
  return parsed;
}

const program = new Command()
  .name("discord-store-migrate")
  .description("Apply this schema's migrations to DATABASE_URL.")
  .option(
    "--wait-timeout <seconds>",
    "Seconds to wait for database readiness before migrating.",
    parseNonNegativeNumber,
    0,
  )
  .action(async (options: { waitTimeout: number }) => {
    const pool = makePool(loadEnv().databaseUrl);
    try {
      await upgrade(pool, { waitTimeout: options.waitTimeout });
    } finally {
      await pool.close();
    }
  });

await program.parseAsync(process.argv);
