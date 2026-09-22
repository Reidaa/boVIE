import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createRailwayContext, project, type ServiceNode } from "railway/iac";
import configuration, { deliveryEnabled } from "./railway.ts";

const spec = await configuration(createRailwayContext({ environment: "staging", projectName: "boVIE" }), project);
const resources = spec.resources!.flat();
const services = resources.filter((resource): resource is ServiceNode => resource.type === "service");
const byName = new Map(services.map((service) => [service.name, service]));
const root = fileURLToPath(new URL("../", import.meta.url));

test("configuration cannot accidentally replace production", async () => {
  await assert.rejects(async () => configuration(createRailwayContext({ environment: "production" }), project), /targets staging/);
});

test("every service has an explicit build, command, and private deployment", () => {
  assert.equal(services.length, 9);
  for (const service of services) {
    if (service.source?.type !== "empty") assert.equal(service.source?.rootDirectory, "/");
    assert.equal(service.build?.builder, "DOCKERFILE");
    assert.ok(existsSync(root + service.build!.dockerfilePath));
    assert.equal(service.deploy?.sleepApplication, false);
    assert.equal(service.networking?.serviceDomains, undefined);
    assert.equal(service.networking?.tcpProxies, undefined);
  }
  for (const name of ["business-france", "wttj"]) {
    const service = byName.get(name)!;
    assert.equal(service.deploy?.restartPolicyType, "NEVER");
    assert.equal(service.deploy?.numReplicas, 1);
    assert.ok(service.deploy?.cronSchedule);
    assert.deepEqual(service.deploy?.preDeployCommand, ["source-migrate --wait-timeout 180"]);
    assert.deepEqual(Object.keys(service.variables!).filter((key) => key.startsWith("NATS_")), []);
  }
});

test("secrets stay with their owner and staging delivery starts stopped", () => {
  for (const service of services) {
    const variables = service.variables ?? {};
    if (service.name !== "mysql") assert.equal(variables.MYSQL_ROOT_PASSWORD, undefined);
    if (service.name !== "discord-delivery") assert.equal(variables.DISCORD_WEBHOOK_URL, undefined);
    if (service.name !== "mysql" && service.name !== "nats") {
      for (const key of Object.keys(variables)) assert.ok(!key.endsWith("DATABASE_PASSWORD"));
    }
  }
  assert.equal(byName.get("broker-setup")!.variables!.DATABASE_URL, undefined);
  const delivery = byName.get("discord-delivery")!;
  assert.equal(delivery.source?.type, deliveryEnabled ? "github" : "empty");
  if (!deliveryEnabled) assert.equal(delivery.source?.repo, undefined);
  assert.equal(byName.get("discord-delivery")!.variables!.NATS_PASSWORD, undefined);
});

test("stateful services require persistent mounts", () => {
  assert.equal(byName.get("mysql")!.deploy?.requiredMountPath, "/var/lib/mysql");
  assert.equal(byName.get("nats")!.deploy?.requiredMountPath, "/data");
  assert.equal(byName.get("mysql")!.volumeAttachments?.["mysql-data"].mountPath, "/var/lib/mysql");
  assert.equal(byName.get("nats")!.volumeAttachments?.["nats-data"].mountPath, "/data");
});

test("each application image installs only its workspace package", () => {
  for (const name of ["business-france", "wttj", "outbox-relay", "notification-intake", "discord-delivery", "broker-setup"]) {
    const dockerfile = readFileSync(`${root}services/${name}/Dockerfile`, "utf8");
    assert.ok(dockerfile.includes(`--package bovie-${name}`));
    assert.ok(dockerfile.includes("--frozen --no-dev --no-editable"));
  }
});
