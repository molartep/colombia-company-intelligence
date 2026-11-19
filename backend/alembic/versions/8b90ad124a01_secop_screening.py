"""SECOP runs, evidence projections and run membership."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "8b90ad124a01"
down_revision = "4e07f6ee2d99"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "screening_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source_id", sa.String(100), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("canonical_nit", sa.String(15), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("summary", postgresql.JSONB()),
        sa.Column("query_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_screening_company_source_started",
        "screening_runs",
        ["company_id", "source_id", "started_at"],
    )
    op.create_table(
        "secop_contracts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "evidence_id",
            sa.Uuid(),
            sa.ForeignKey("source_records.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("contract_id", sa.String(300), nullable=False),
        sa.Column("buyer", sa.String(1000)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("modality", sa.String(500)),
        sa.Column("signature_date", sa.Date()),
        sa.Column("value", sa.Numeric(31, 6)),
        sa.Column("normalized", postgresql.JSONB(), nullable=False),
    )
    for field in ("contract_id", "buyer", "status", "modality", "signature_date", "value"):
        op.create_index(f"ix_secop_contracts_{field}", "secop_contracts", [field])
    op.create_table(
        "screening_contracts",
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("screening_runs.id"), primary_key=True),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("secop_contracts.id"), primary_key=True),
    )


def downgrade():
    op.drop_table("screening_contracts")
    op.drop_table("secop_contracts")
    op.drop_table("screening_runs")
