"""Record the research mode chosen for each investigation."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # Existing investigations ran with the budget that is now called balanced.
    op.add_column(
        "investigations",
        sa.Column(
            "research_mode", sa.String(20), nullable=False, server_default=sa.text("'balanced'")
        ),
    )


def downgrade():
    op.drop_column("investigations", "research_mode")
