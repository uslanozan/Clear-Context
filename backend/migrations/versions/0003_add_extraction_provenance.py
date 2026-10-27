"""Preserve claim spans and bounded extraction coverage."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "claims", sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
    )
    op.add_column("investigations", sa.Column("extraction_coverage", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("investigations", "extraction_coverage")
    op.drop_column("claims", "provenance")
