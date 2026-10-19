import assert from "node:assert/strict";
import { test } from "node:test";
import { credentials, missingCredentials } from "./secrets.ts";

test("first broker deployment receives independent URL-safe random passwords", () => {
  const first = missingCredentials("nats", {});
  const second = missingCredentials("nats", {});
  assert.deepEqual(Object.keys(first), credentials.nats);
  assert.equal(new Set(Object.values(first)).size, 4);
  for (const key of credentials.nats) {
    assert.match(first[key], /^bovie_[a-f0-9]{64}$/);
    assert.notEqual(first[key], second[key]);
  }
});

test("repeat deployments retain existing and sealed credentials", () => {
  assert.deepEqual(
    missingCredentials("nats", {
      NATS_SETUP_PASSWORD: "existing",
      NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD: null,
      NATS_COLLECTOR_WTTJ_PASSWORD: "existing",
      NATS_DISCORD_INTAKE_PASSWORD: "existing",
    }),
    {},
  );
  assert.deepEqual(
    Object.keys(
      missingCredentials("nats", {
        NATS_SETUP_PASSWORD: "existing",
        NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD: "",
        NATS_COLLECTOR_WTTJ_PASSWORD: null,
      }),
    ),
    ["NATS_COLLECTOR_BUSINESS_FRANCE_PASSWORD", "NATS_DISCORD_INTAKE_PASSWORD"],
  );
});
