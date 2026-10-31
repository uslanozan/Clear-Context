"""research summary per report, and reruns or continuations of a report

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("investigations") as batch:
        batch.add_column(sa.Column("research_summary", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("parent_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("relation", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("investigations") as batch:
        batch.drop_column("relation")
        batch.drop_column("parent_id")
        batch.drop_column("research_summary")
