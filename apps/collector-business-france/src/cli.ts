#!/usr/bin/env bun
import { configureLogging, loadEnvironment, logger } from "@bovie/cli-common";
import { type DbPool, makePool } from "@bovie/mysql-common";
import { loadEnv } from "@bovie/mysql-common/env";
import { Publisher } from "@bovie/nats-client";
import type { OfferEvent } from "@bovie/offer-events";
import { Command, InvalidArgumentError } from "commander";
import { configFromParams } from "./config.js";
import { getCountryNames, getSpecializationNames, getZoneNames } from "./datasets.js";
import { DEFAULT_OFFER_LIMIT, task } from "./index.js";
import { createSearchParameters, type SearchParameters } from "./job.js";

const VERSION = "0.4.0";

function parsePositiveInt(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new InvalidArgumentError("Must be an integer >= 1");
  }
  return parsed;
}

function parseBooleanEnv(value: string | undefined): boolean {
  if (!value) {
    return false;
  }
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

function splitCommaEnv(value: string | undefined): string[] {
  if (!value?.trim()) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function validateChoice(allowed: readonly string[], label: string) {
  const lookup = new Set(allowed.map((item) => item.toLowerCase()));
  return (value: string, previous: string[]): string[] => {
    if (!lookup.has(value.trim().toLowerCase())) {
      throw new InvalidArgumentError(`Invalid ${label}: ${value}`);
    }
    return [...previous, value.trim()];
  };
}

export interface PublisherLike {
  connect(): Promise<unknown>;
  publish(event: OfferEvent): Promise<void>;
  close(): Promise<void>;
}

export interface CliRuntime {
  makePool?: typeof makePool;
  createPublisher?: () => PublisherLike;
  runTask?: (
    params: SearchParameters,
    pool: DbPool,
    publish: (event: OfferEvent) => Promise<void> | void,
  ) => Promise<void>;
}

export async function runCli(argv: string[], runtime: CliRuntime = {}): Promise<void> {
  // Load .env before resolving environment-backed options.
  loadEnvironment();

  const zones = getZoneNames();
  const countries = getCountryNames();
  const specializations = getSpecializationNames();

  const defaultLimit = process.env.BUSINESS_FRANCE_LIMIT
    ? parsePositiveInt(process.env.BUSINESS_FRANCE_LIMIT)
    : DEFAULT_OFFER_LIMIT;
  const defaultDebug = parseBooleanEnv(process.env.BUSINESS_FRANCE_DEBUG);
  const envZones = splitCommaEnv(process.env.BUSINESS_FRANCE_REGION);
  const envCountries = splitCommaEnv(process.env.BUSINESS_FRANCE_COUNTRY);
  const envSpecs = splitCommaEnv(process.env.BUSINESS_FRANCE_SPECIALIZATION);

  const program = new Command()
    .name("collector-business-france")
    .description("Discover VIE/VIA opportunities from Business France.")
    .version(`Bovie ${VERSION}`, "--version")
    .option("--debug", "Enable debug logging", defaultDebug)
    .option(
      "--limit <number>",
      `Maximum search results to inspect (default: ${DEFAULT_OFFER_LIMIT})`,
      parsePositiveInt,
      defaultLimit,
    )
    .option(
      "-g, --geozone <zone>",
      "Regions to filter on",
      validateChoice(zones, "geographic zone"),
      [] as string[],
    )
    .option(
      "-c, --country <country>",
      "Countries to filter on",
      validateChoice(countries, "country"),
      [] as string[],
    )
    .option(
      "-s, --specialization <specialization>",
      "Specializations to filter on",
      validateChoice(specializations, "specialization"),
      [] as string[],
    )
    .action(
      async (options: {
        debug: boolean;
        limit: number;
        geozone: string[];
        country: string[];
        specialization: string[];
      }) => {
        const selectedZones = options.geozone.length > 0 ? options.geozone : envZones;
        const selectedCountries = options.country.length > 0 ? options.country : envCountries;
        const selectedSpecs = options.specialization.length > 0 ? options.specialization : envSpecs;

        configureLogging({ debug: options.debug });

        const config = configFromParams({
          limit: options.limit,
          regions: selectedZones,
          specializations: selectedSpecs,
          countries: selectedCountries,
        });
        const params = createSearchParameters({
          limit: config.search.limit,
          specializationsIds: [...config.search.specializations],
          countriesIds: [...config.search.countries],
        });

        logger.debug(`limit: ${options.limit}`);
        logger.debug(`geozones: ${JSON.stringify(selectedZones)}`);
        logger.debug(`specializations: ${JSON.stringify(selectedSpecs)}`);
        logger.debug(`countries: ${JSON.stringify(selectedCountries)}`);
        logger.debug(`Config: ${JSON.stringify(config)}`);

        logger.info("Starting ...");
        const poolFactory = runtime.makePool ?? makePool;
        const publisherFactory = runtime.createPublisher ?? (() => new Publisher());
        const executeTask = runtime.runTask ?? ((p, db, pub) => task(p, db, pub));

        const pool = poolFactory(loadEnv().databaseUrl);
        try {
          const publisher = publisherFactory();
          await publisher.connect();
          try {
            await executeTask(params, pool, (event) => publisher.publish(event));
          } finally {
            await publisher.close();
          }
        } catch (error) {
          logger.exception("Business France collection failed", error);
          throw new Error("Business France collection failed");
        } finally {
          await pool.close();
        }
        logger.info("Done ...");
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
