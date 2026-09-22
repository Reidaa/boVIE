"""Notification-owned inbox and retryable deliveries."""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "notification_0001"
down_revision = None
branch_labels = None
depends_on = None

OPTIONS: dict[str, Any] = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_bin",
}


def upgrade():
    op.create_table(
        "inbox",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", DATETIME(fsp=6), nullable=False),
        **OPTIONS,
    )
    op.create_table(
        "deliveries",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", DATETIME(fsp=6), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("lease_until", DATETIME(fsp=6)),
        sa.Column("completed_at", DATETIME(fsp=6)),
        **OPTIONS,
    )
    op.create_index("ix_deliveries_available_at", "deliveries", ["available_at"])


def downgrade():
    op.drop_table("deliveries")
    op.drop_table("inbox")
