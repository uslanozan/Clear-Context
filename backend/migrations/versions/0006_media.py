"""Store uploaded media and the text analyzed alongside the user's input."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "media",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("storage_name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("finding", sa.JSON(), nullable=True),
    )
    op.create_index("ix_media_investigation_id", "media", ["investigation_id"])
    op.add_column("investigations", sa.Column("analyzed_text", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("investigations", "analyzed_text")
    op.drop_index("ix_media_investigation_id", table_name="media")
    op.drop_table("media")
