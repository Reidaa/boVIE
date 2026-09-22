import assert from "node:assert/strict";
import { test } from "node:test";
import { credentials, missingCredentials } from "./secrets.ts";

test("first deployment receives independent URL-safe random passwords", () => {
  const first = missingCredentials("mysql", {});
  const second = missingCredentials("mysql", {});
  assert.deepEqual(Object.keys(first), credentials.mysql);
  assert.equal(new Set(Object.values(first)).size, 4);
  for (const key of credentials.mysql) {
    assert.match(first[key], /^[a-f0-9]{64}$/);
    assert.notEqual(first[key], second[key]);
  }
});

test("repeat deployments retain existing and sealed credentials", () => {
  assert.deepEqual(missingCredentials("nats", {
    NATS_ADMIN_PASSWORD: "existing", NATS_BF_PASSWORD: null,
    NATS_WTTJ_PASSWORD: "existing", NATS_NOTIFICATIONS_PASSWORD: "existing",
  }), {});
  assert.deepEqual(Object.keys(missingCredentials("mysql", {
    MYSQL_ROOT_PASSWORD: "existing", BF_DATABASE_PASSWORD: "", WTTJ_DATABASE_PASSWORD: null,
  })), ["BF_DATABASE_PASSWORD", "NOTIFICATION_DATABASE_PASSWORD"]);
});
