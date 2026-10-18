"""Record when each scan last returned results, to detect a silent source."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "collector_store_0002"
down_revision = "collector_store_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "checkpoints",
        sa.Column("results_seen_at", DATETIME(fsp=6), nullable=True),
    )


def downgrade():
    op.drop_column("checkpoints", "results_seen_at")
