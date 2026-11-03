"""a title the user gives an investigation in the history list

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("title", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("investigations", "title")
