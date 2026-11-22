CREATE TABLE offers (
    source_offer_id VARCHAR(255) NOT NULL PRIMARY KEY,
    observed_at DATETIME(6) NOT NULL,
    event_id VARCHAR(36) NOT NULL UNIQUE,
    payload JSON NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    last_seen_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE checkpoints (
    scan VARCHAR(64) NOT NULL PRIMARY KEY,
    offset INTEGER NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
