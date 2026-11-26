"""Isolated append-only government involvement evaluations."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b6a7203c9101"
down_revision = "8b90ad124a01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "government_involvement_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id")),
        sa.Column("screening_run_id", sa.Uuid(), sa.ForeignKey("screening_runs.id")),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("execution_mode", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_involvement_cache",
        "government_involvement_evaluations",
        ["input_fingerprint", "created_at"],
    )


def downgrade():
    op.drop_table("government_involvement_evaluations")
