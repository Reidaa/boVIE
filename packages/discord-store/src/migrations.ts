import type { Migration } from "@bovie/mysql-common/migrate";

export const DISCORD_MIGRATIONS: readonly Migration[] = [
  {
    version: "discord_store_0001",
    legacyAlembicRevisions: ["discord_store_0001"],
    async up(conn) {
      await conn.query(`
        CREATE TABLE inbox (
          event_id VARCHAR(36) NOT NULL,
          payload JSON NOT NULL,
          received_at DATETIME(6) NOT NULL,
          PRIMARY KEY (event_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
      `);
      await conn.query(`
        CREATE TABLE deliveries (
          event_id VARCHAR(36) NOT NULL,
          payload JSON NOT NULL,
          attempts INT NOT NULL,
          available_at DATETIME(6) NOT NULL,
          claim_token VARCHAR(36) NULL,
          lease_until DATETIME(6) NULL,
          completed_at DATETIME(6) NULL,
          PRIMARY KEY (event_id),
          KEY ix_deliveries_available_at (available_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
      `);
    },
  },
];
