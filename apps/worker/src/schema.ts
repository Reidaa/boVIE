import { bigint, jsonb, pgTable, text, timestamp, uuid } from "drizzle-orm/pg-core";

import type { JobDiscoveredEvent } from "./types.js";

export const bovieJob = pgTable("bovie_job", {
  id: uuid("id").primaryKey(),
  offerId: bigint("offer_id", { mode: "number" }).notNull().unique(),
  source: text("source").notNull(),
  payload: jsonb("payload").$type<JobDiscoveredEvent>().notNull(),
  discoveredAt: timestamp("discovered_at", { withTimezone: true }),
  processedAt: timestamp("processed_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});
