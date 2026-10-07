"""Collectors publish directly: drop the outbox and track offer content and sightings.

MySQL commits each DDL statement on its own, so every step can be rerun after a
partial failure, and the destructive step comes last.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "source_0002"
down_revision = "source_0001"
branch_labels = None
depends_on = None

RETIRED = "retired_outbox"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("offers")}
    if "content_hash" not in columns:
        op.add_column("offers", sa.Column("content_hash", sa.String(64)))
    if "last_seen_at" not in columns:
        op.add_column("offers", sa.Column("last_seen_at", DATETIME(fsp=6)))
    op.execute(
        "UPDATE offers SET last_seen_at = observed_at WHERE last_seen_at IS NULL"
    )

    tables = set(inspector.get_table_names())
    if "outbox" in tables:
        # Rename before counting: a previous-release collector or relay that is
        # still running now fails on the missing table and retries later, so no
        # event can be written between the count and the drop.
        op.rename_table("outbox", RETIRED)
    elif RETIRED not in tables:
        return
    pending = bind.scalar(
        sa.text(f"SELECT COUNT(*) FROM {RETIRED} WHERE completed_at IS NULL")
    )
    if pending:
        op.rename_table(RETIRED, "outbox")
        raise RuntimeError(
            f"The outbox still holds {pending} unpublished events. Run the previous "
            "release's `outbox-relay --once` for this source, then migrate again."
        )
    op.drop_table(RETIRED)


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
