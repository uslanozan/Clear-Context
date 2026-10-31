"""links read from the user's text, and the page an image came from

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("finding", sa.JSON(), nullable=False),
    )
    op.create_index("ix_links_investigation_id", "links", ["investigation_id"])
    with op.batch_alter_table("media") as batch:
        batch.add_column(sa.Column("source_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("media") as batch:
        batch.drop_column("source_url")
    op.drop_index("ix_links_investigation_id", table_name="links")
    op.drop_table("links")
