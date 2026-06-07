"""Add unique offer id constraint.

Revision ID: 202606051335
Revises:
Create Date: 2026-06-05 13:35:00

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "202606051335"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "bovie_job"
CONSTRAINT_NAME = "uq_bovie_job_offer_id"


def _has_unique_offer_constraint() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints(TABLE_NAME)
    indexes = inspector.get_indexes(TABLE_NAME)

    return any(
        constraint["name"] == CONSTRAINT_NAME for constraint in constraints
    ) or any(index["name"] == CONSTRAINT_NAME and index.get("unique") for index in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("offer_id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("offer_id", name=CONSTRAINT_NAME),
        )
        return

    op.execute(
        sa.text(
            """
            WITH ranked_jobs AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY offer_id
                        ORDER BY id
                    ) AS row_number
                FROM bovie_job
            )
            DELETE FROM bovie_job
            WHERE id IN (
                SELECT id
                FROM ranked_jobs
                WHERE row_number > 1
            )
            """
        )
    )

    if not _has_unique_offer_constraint():
        op.create_unique_constraint(CONSTRAINT_NAME, TABLE_NAME, ["offer_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table(TABLE_NAME) and _has_unique_offer_constraint():
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="unique")
