"""Index snapshot-scoped involvement history for authorized live evaluation."""

from alembic import op

revision = "c7902ea3b112"
down_revision = "b6a7203c9101"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_involvement_company_run_created",
        "government_involvement_evaluations",
        ["company_id", "screening_run_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_involvement_company_run_created", "government_involvement_evaluations")
