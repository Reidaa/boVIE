import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createRailwayContext, project, type DatabaseNode, type ServiceNode } from "railway/iac";
import configuration, { deliveryEnabled } from "./railway.ts";

const spec = await configuration(
  createRailwayContext({ environment: "staging", projectName: "boVIE" }),
  project,
);
const resources = spec.resources!.flat();
const services = resources.filter(
  (resource): resource is ServiceNode => resource.type === "service",
);
const databases = resources.filter(
  (resource): resource is DatabaseNode => resource.type === "database",
);
const byName = new Map(services.map((service) => [service.name, service]));
const root = fileURLToPath(new URL("../", import.meta.url));

test("configuration cannot accidentally replace production", async () => {
  await assert.rejects(
    async () => configuration(createRailwayContext({ environment: "production" }), project),
    /targets staging/,
  );
});

test("every service has an explicit build, command, and private deployment", () => {
  assert.equal(services.length, 8);
  for (const service of services) {
    if (service.source) assert.equal(service.source?.rootDirectory, "/");
    assert.equal(service.build?.builder, "DOCKERFILE");
    assert.ok(existsSync(root + service.build!.dockerfilePath));
    assert.equal(service.deploy?.multiRegionConfig?.["europe-west4-drams3a"]?.numReplicas, 1);
    assert.equal(service.networking?.serviceDomains, undefined);
    assert.equal(service.networking?.tcpProxies, undefined);
  }
  for (const name of ["business-france", "wttj"]) {
    const service = byName.get(name)!;
    assert.equal(service.deploy?.restartPolicyType, "NEVER");
    assert.equal(service.deploy?.restartPolicyMaxRetries, undefined);
    assert.ok(service.deploy?.cronSchedule);
    assert.deepEqual(service.deploy?.preDeployCommand, ["source-migrate --wait-timeout 180"]);
    assert.deepEqual(
      Object.keys(service.variables!).filter((key) => key.startsWith("NATS_")),
      [],
    );
  }
});

test("secrets stay with their owner and staging delivery starts stopped", () => {
  for (const service of services) {
    const variables = service.variables ?? {};
    assert.equal(variables.MYSQL_ROOT_PASSWORD, undefined);
    if (service.name !== "discord-delivery") assert.equal(variables.DISCORD_WEBHOOK_URL, undefined);
    for (const key of Object.keys(variables)) assert.ok(!key.endsWith("DATABASE_PASSWORD"));
  }
  assert.equal(byName.get("broker-setup")!.variables!.DATABASE_URL, undefined);
  const delivery = byName.get("discord-delivery")!;
  assert.equal(delivery.source?.type, deliveryEnabled ? "github" : undefined);
  if (!deliveryEnabled) assert.equal(delivery.source?.repo, undefined);
  assert.equal(byName.get("discord-delivery")!.variables!.NATS_PASSWORD, undefined);
});

test("stateful services require persistent mounts", () => {
  assert.deepEqual(
    databases.map((database) => database.name),
    ["mysql-business-france", "mysql-wttj", "mysql-notifications"],
  );
  for (const database of databases) {
    assert.equal(database.engine, "mysql");
    assert.equal(database.source?.image, "mysql:9");
    assert.equal(database.deploy?.multiRegionConfig?.["europe-west4-drams3a"]?.numReplicas, 1);
  }
  for (const [service, database] of [
    ["business-france", "mysql-business-france"],
    ["relay-bf", "mysql-business-france"],
    ["wttj", "mysql-wttj"],
    ["relay-wttj", "mysql-wttj"],
    ["notification-intake", "mysql-notifications"],
    ["discord-delivery", "mysql-notifications"],
  ]) {
    assert.deepEqual(byName.get(service)!.variables!.DATABASE_URL, {
      type: "reference",
      resource: `database.${database}`,
      output: "MYSQL_URL",
    });
  }
  assert.equal(byName.get("nats")!.deploy?.requiredMountPath, "/data");
  assert.equal(byName.get("nats")!.volumeAttachments?.["nats-data"].mountPath, "/data");
});

test("each application image installs only its workspace package", () => {
  for (const name of [
    "business-france",
    "wttj",
    "outbox-relay",
    "notification-intake",
    "discord-delivery",
    "broker-setup",
  ]) {
    const dockerfile = readFileSync(`${root}services/${name}/Dockerfile`, "utf8");
    assert.ok(dockerfile.includes(`--package bovie-${name}`));
    assert.ok(dockerfile.includes("--frozen --no-dev --no-editable"));
  }
});
