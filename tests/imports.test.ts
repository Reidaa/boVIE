import { describe, test } from "bun:test";
import { execFileSync } from "node:child_process";

describe("service imports", () => {
  test("imports do not open a database connection", () => {
    const cleanEnv = { ...process.env };
    delete cleanEnv.DATABASE_URL;
    execFileSync(
      "bun",
      [
        "-e",
        `
        import mysql from "mysql2/promise";
        mysql.createPool = () => { throw new Error("Import attempted to create a pool"); };
        mysql.createConnection = () => { throw new Error("Import attempted to create a connection"); };
        await import("@bovie/mysql-common/env");
        await import("@bovie/mysql-common");
        await import("@bovie/collector-business-france");
      `,
      ],
      { env: cleanEnv, stdio: "pipe" },
    );
  });
});
