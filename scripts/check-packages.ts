/**
 * Deploy each app into an isolated directory with `pnpm deploy` and verify its
 * deployable interface, packaged migrations, and dependency isolation.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

interface ServiceSpec {
  readonly packageName: string;
  readonly command: string;
  readonly migrations: readonly string[];
  readonly migrationPackage: string;
  readonly forbiddenPackages: readonly string[];
}

const SERVICES: Record<string, ServiceSpec> = {
  "collector-business-france": {
    packageName: "@bovie/collector-business-france",
    command: "collector-business-france",
    migrations: ["collector-store-migrate"],
    migrationPackage: "@bovie/collector-store",
    forbiddenPackages: ["@bovie/discord-store"],
  },
  "collector-wttj": {
    packageName: "@bovie/collector-wttj",
    command: "collector-wttj",
    migrations: ["collector-store-migrate"],
    migrationPackage: "@bovie/collector-store",
    forbiddenPackages: ["@bovie/collector-business-france", "@bovie/discord-store"],
  },
  "collector-workday": {
    packageName: "@bovie/collector-workday",
    command: "collector-workday",
    migrations: ["collector-store-migrate"],
    migrationPackage: "@bovie/collector-store",
    forbiddenPackages: ["@bovie/discord-store"],
  },
  "discord-intake": {
    packageName: "@bovie/discord-intake",
    command: "discord-intake",
    migrations: ["discord-store-migrate"],
    migrationPackage: "@bovie/discord-store",
    forbiddenPackages: ["@bovie/collector-store"],
  },
  "discord-sender": {
    packageName: "@bovie/discord-sender",
    command: "discord-sender",
    migrations: ["discord-store-migrate"],
    migrationPackage: "@bovie/discord-store",
    forbiddenPackages: [
      "@bovie/nats-client",
      "@nats-io/transport-node",
      "@nats-io/jetstream",
      "@bovie/collector-store",
    ],
  },
};

const ROOT = resolve(import.meta.dirname, "..");

function run(command: string, args: string[], cwd: string, env: NodeJS.ProcessEnv): string {
  return execFileSync(command, args, {
    cwd,
    env,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function main(): void {
  const cleanEnv: NodeJS.ProcessEnv = { ...process.env };
  delete cleanEnv.DATABASE_URL;
  delete cleanEnv.DISCORD_WEBHOOK_URL;

  const allServices = Object.entries(SERVICES);

  for (const [service, spec] of allServices) {
    const tempDir = mkdtempSync(join(tmpdir(), `bovie-${service}-`));
    try {
      const deployDir = join(tempDir, "app");
      run(
        "pnpm",
        ["deploy", `--filter=${spec.packageName}`, "--prod", "--legacy", deployDir],
        ROOT,
        cleanEnv,
      );

      const blocked = [
        ...spec.forbiddenPackages,
        ...allServices
          .filter(([other]) => other !== service)
          .map(([, otherSpec]) => otherSpec.packageName),
      ];

      for (const pkg of blocked) {
        const pkgPath = join(deployDir, "node_modules", ...pkg.split("/"));
        if (existsSync(pkgPath)) {
          throw new Error(`Unexpected dependency ${pkg} installed in ${service}`);
        }
      }

      const migrationDist = join(
        deployDir,
        "node_modules",
        ...spec.migrationPackage.split("/"),
        "dist",
        "migrations.js",
      );
      if (!existsSync(migrationDist)) {
        throw new Error(`Missing packaged migrations at ${migrationDist} for ${service}`);
      }

      const binDir = join(deployDir, "node_modules", ".bin");
      const appEntry = join(deployDir, "dist", "cli.js");
      if (!existsSync(appEntry)) {
        throw new Error(`Missing app entrypoint ${appEntry}`);
      }
      run(appEntry, ["--help"], deployDir, cleanEnv);

      for (const migration of spec.migrations) {
        const binPath = join(binDir, migration);
        if (!existsSync(binPath)) {
          throw new Error(`Missing bin entrypoint ${migration} in ${binDir}`);
        }
        run(binPath, ["--help"], deployDir, cleanEnv);
      }

      if (service === "collector-business-france") {
        const output = run(appEntry, ["--version"], deployDir, cleanEnv).trim();
        if (!output.startsWith("Bovie ")) {
          throw new Error(`Unexpected --version output: ${output}`);
        }
      }

      const entrypoints = [spec.command, ...spec.migrations];

      process.stdout.write(
        `${JSON.stringify({
          service,
          isolated_install: "passed",
          commands: entrypoints,
        })}\n`,
      );
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
}

main();
