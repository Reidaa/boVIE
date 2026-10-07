"""Collectors publish directly: drop the outbox and track offer content and sightings."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "source_0002"
down_revision = "source_0001"
branch_labels = None
depends_on = None


def upgrade():
    pending = op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM outbox WHERE completed_at IS NULL")
    )
    if pending:
        raise RuntimeError(
            f"The outbox still holds {pending} unpublished events. Run the previous "
            "release's `outbox-relay --once` for this source, then migrate again."
        )
    op.drop_table("outbox")
    op.add_column("offers", sa.Column("content_hash", sa.String(64)))
    op.add_column("offers", sa.Column("last_seen_at", DATETIME(fsp=6)))
    op.execute("UPDATE offers SET last_seen_at = observed_at")


def downgrade():
    op.drop_column("offers", "last_seen_at")
    op.drop_column("offers", "content_hash")
    op.create_table(
        "outbox",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", DATETIME(fsp=6), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("lease_until", DATETIME(fsp=6)),
        sa.Column("completed_at", DATETIME(fsp=6)),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_bin",
    )
    op.create_index("ix_outbox_available_at", "outbox", ["available_at"])
