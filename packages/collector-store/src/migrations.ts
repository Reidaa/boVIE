import type { Migration } from "@bovie/mysql-common/migrate";

export const COLLECTOR_MIGRATIONS: readonly Migration[] = [
  {
    version: "collector_store_0001",
    legacyAlembicRevisions: ["collector_store_0001", "collector_store_0002"],
    async up(conn) {
      await conn.query(`
        CREATE TABLE offers (
          source_offer_id VARCHAR(255) NOT NULL,
          observed_at DATETIME(6) NOT NULL,
          event_id VARCHAR(36) NOT NULL,
          payload JSON NOT NULL,
          content_hash VARCHAR(64) NOT NULL,
          last_seen_at DATETIME(6) NOT NULL,
          PRIMARY KEY (source_offer_id),
          UNIQUE KEY uq_offers_event_id (event_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
      `);
      await conn.query(`
        CREATE TABLE checkpoints (
          scan VARCHAR(64) NOT NULL,
          \`offset\` INT NOT NULL,
          PRIMARY KEY (scan)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin
      `);
    },
  },
  {
    version: "collector_store_0002",
    legacyAlembicRevisions: ["collector_store_0002"],
    async up(conn) {
      await conn.query("ALTER TABLE checkpoints ADD COLUMN results_seen_at DATETIME(6) NULL");
    },
  },
];
