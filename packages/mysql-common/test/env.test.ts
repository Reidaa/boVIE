import { describe, expect, test } from "bun:test";
import { inspect } from "node:util";
import { Env } from "../src/env.js";

describe("mysql configuration", () => {
  test("MySQL URL validation and password redaction", () => {
    const settings = new Env({ DATABASE_URL: "mysql+pymysql://worker:secret@localhost/source" });
    expect(settings.databaseUrl.user).toBe("worker");
    expect(settings.databaseUrl.database).toBe("source");
    expect(inspect(settings)).not.toContain("secret");
    expect(String(settings)).not.toContain("secret");

    const railway = new Env({ DATABASE_URL: "mysql://worker:p%40ss@localhost/source" });
    expect(railway.databaseUrl.password).toBe("p@ss");

    for (const url of [
      "postgresql://u:p@host/db",
      "sqlite://",
      "mysql://u:p@host",
      "not a url",
      "mysql://u:p@host:port/db",
    ]) {
      expect(() => new Env({ DATABASE_URL: url })).toThrow();
    }
  });
});
