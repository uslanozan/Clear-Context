"""named groups that organize the history list

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "history_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    # No foreign key: a group is only a label, and deleting one just ungroups its investigations.
    op.add_column("investigations", sa.Column("group_id", sa.String(36), nullable=True))
    op.create_index("ix_investigations_group_id", "investigations", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_investigations_group_id", table_name="investigations")
    op.drop_column("investigations", "group_id")
    op.drop_table("history_groups")
