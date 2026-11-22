CREATE TABLE inbox (
    event_id VARCHAR(36) NOT NULL PRIMARY KEY,
    payload JSON NOT NULL,
    received_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE deliveries (
    event_id VARCHAR(36) NOT NULL PRIMARY KEY,
    payload JSON NOT NULL,
    attempts INTEGER NOT NULL,
    available_at DATETIME(6) NOT NULL,
    claim_token VARCHAR(36) NULL,
    lease_until DATETIME(6) NULL,
    completed_at DATETIME(6) NULL,
    INDEX ix_deliveries_available_at (available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
