"""Source-owned offers, discovery outbox and scan checkpoints."""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "source_0001"
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
        "offers",
        sa.Column("source_offer_id", sa.String(255), primary_key=True),
        sa.Column("observed_at", DATETIME(fsp=6), nullable=False),
        sa.Column("event_id", sa.String(36), unique=True),
        sa.Column("payload", sa.JSON()),
        **OPTIONS,
    )
    op.create_table(
        "outbox",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", DATETIME(fsp=6), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("lease_until", DATETIME(fsp=6)),
        sa.Column("completed_at", DATETIME(fsp=6)),
        **OPTIONS,
    )
    op.create_index("ix_outbox_available_at", "outbox", ["available_at"])
    op.create_table(
        "checkpoints",
        sa.Column("scan", sa.String(64), primary_key=True),
        sa.Column("offset", sa.Integer(), nullable=False),
        **OPTIONS,
    )


def downgrade():
    op.drop_table("checkpoints")
    op.drop_table("outbox")
    op.drop_table("offers")
