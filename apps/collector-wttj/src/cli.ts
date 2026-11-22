#!/usr/bin/env bun
import { configureLogging, loadEnvironment, logger } from "@bovie/cli-common";
import { type DbPool, makePool } from "@bovie/mysql-common";
import { loadEnv } from "@bovie/mysql-common/env";
import { Publisher } from "@bovie/nats-client";
import type { OfferEvent } from "@bovie/offer-events";
import { Command, InvalidArgumentError } from "commander";
import { type CollectOptions, collect, type FetchLike } from "./index.js";

function parsePositiveInt(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new InvalidArgumentError("Must be an integer >= 1");
  }
  return parsed;
}

function appendOption(value: string, previous: string[]): string[] {
  return [...previous, value];
}

function splitWhitespaceEnv(value: string | undefined): string[] {
  if (!value?.trim()) {
    return [];
  }
  return value.trim().split(/\s+/);
}

export interface PublisherLike {
  connect(): Promise<unknown>;
  publish(event: OfferEvent): Promise<void>;
  close(): Promise<void>;
}

export interface WttjCliRuntime {
  makePool?: typeof makePool;
  createPublisher?: () => PublisherLike;
  runCollect?: (
    pool: DbPool,
    fetchFn: FetchLike,
    publish: (event: OfferEvent) => Promise<void> | void,
    options: CollectOptions,
  ) => Promise<void>;
}

export async function runCli(argv: string[], runtime: WttjCliRuntime = {}): Promise<void> {
  loadEnvironment();

  const defaultQuery = process.env.WTTJ_QUERY ?? "";
  const defaultLimit = process.env.WTTJ_LIMIT ? parsePositiveInt(process.env.WTTJ_LIMIT) : 50;
  const defaultMaxPages = process.env.WTTJ_MAX_PAGES
    ? parsePositiveInt(process.env.WTTJ_MAX_PAGES)
    : 5;
  const envContracts = splitWhitespaceEnv(process.env.WTTJ_CONTRACTS);

  const program = new Command()
    .name("collector-wttj")
    .description("Discover published jobs of any contract type on Welcome to the Jungle.")
    .option("--query <text>", "Optional job title search; empty includes all titles.", defaultQuery)
    .option(
      "--limit <number>",
      "Maximum search results to inspect.",
      parsePositiveInt,
      defaultLimit,
    )
    .option("--max-pages <number>", "Maximum pages to inspect.", parsePositiveInt, defaultMaxPages)
    .option("--country <code>", "ISO country code, e.g. CA.", appendOption, [] as string[])
    .option(
      "--contract <type>",
      "Optional WTTJ contract type (repeatable), e.g. full_time or internship.",
      appendOption,
      [] as string[],
    )
    .action(
      async (options: {
        query: string;
        limit: number;
        maxPages: number;
        country: string[];
        contract: string[];
      }) => {
        configureLogging();
        const contracts = (options.contract.length > 0 ? options.contract : envContracts).map((c) =>
          c.toLowerCase(),
        );
        const countries = options.country.map((c) => c.toUpperCase());

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
              {
                query: options.query,
                limit: options.limit,
                maxPages: options.maxPages,
                countries,
                contracts,
              },
            );
          } finally {
            await publisher.close();
          }
        } catch (error) {
          logger.exception("WTTJ collection failed", error);
          throw new Error("WTTJ collection failed; retry will replay discovery");
        } finally {
          await pool.close();
        }
      },
    );

  await program.parseAsync(argv);
}

if (import.meta.main) {
  runCli(process.argv).catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exit(1);
  });
}
