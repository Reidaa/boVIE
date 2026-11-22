#!/usr/bin/env bun
import { configureLogging, loadEnvironment, logger } from "@bovie/cli-common";
import { type DbPool, makePool } from "@bovie/mysql-common";
import { loadEnv } from "@bovie/mysql-common/env";
import { Publisher } from "@bovie/nats-client";
import type { OfferEvent } from "@bovie/offer-events";
import { Command, InvalidArgumentError } from "commander";
import type { Board } from "./api.js";
import {
  BoardValidationError,
  collect,
  type FetchLike,
  loadBoards,
  type WorkdayCollectOptions,
} from "./index.js";

function parsePositiveInt(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new InvalidArgumentError("Must be an integer >= 1");
  }
  return parsed;
}

export class CliUsageError extends Error {
  readonly exitCode = 2;

  constructor(message: string) {
    super(message);
    this.name = "CliUsageError";
  }
}

export interface PublisherLike {
  connect(): Promise<unknown>;
  publish(event: OfferEvent): Promise<void>;
  close(): Promise<void>;
}

export interface WorkdayCliRuntime {
  makePool?: typeof makePool;
  createPublisher?: () => PublisherLike;
  runCollect?: (
    pool: DbPool,
    fetchFn: FetchLike,
    publish: (event: OfferEvent) => Promise<void> | void,
    boards: readonly Board[],
    options: WorkdayCollectOptions,
  ) => Promise<void>;
}

export async function runCli(argv: string[], runtime: WorkdayCliRuntime = {}): Promise<void> {
  loadEnvironment();

  const defaultBoards = process.env.WORKDAY_BOARDS ?? "";
  const defaultLimit = process.env.WORKDAY_LIMIT ? parsePositiveInt(process.env.WORKDAY_LIMIT) : 40;

  const program = new Command()
    .name("collector-workday")
    .description("Discover new jobs on the configured Workday career sites.")
    .option("--boards <json>", "Required JSON list of boards to collect.", defaultBoards)
    .option(
      "--limit <number>",
      "Maximum job postings to inspect per board.",
      parsePositiveInt,
      defaultLimit,
    )
    .action(async (options: { boards: string; limit: number }) => {
      configureLogging();
      // Fail on configuration before connecting to MySQL or NATS.
      let boards: Board[];
      try {
        boards = loadBoards(options.boards);
      } catch (error) {
        const message =
          error instanceof BoardValidationError
            ? error.message
            : `Invalid WORKDAY_BOARDS: ${String(error)}`;
        throw new CliUsageError(message);
      }

      const poolFactory = runtime.makePool ?? makePool;
      const publisherFactory = runtime.createPublisher ?? (() => new Publisher());
      const executeCollect = runtime.runCollect ?? collect;

      const pool = poolFactory(loadEnv().databaseUrl);
      try {
        const publisher = publisherFactory();
        await publisher.connect();
        try {
          await executeCollect(
            pool,
            (input, init) => fetch(input, init),
            (event) => publisher.publish(event),
            boards,
            { limit: options.limit },
          );
        } finally {
          await publisher.close();
        }
      } catch (error) {
        logger.exception("Workday collection failed", error);
        throw new Error("Workday collection failed; retry will replay discovery");
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
    process.exit(error instanceof CliUsageError ? error.exitCode : 1);
  });
}
