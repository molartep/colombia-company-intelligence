"""Create company identity and provenance tables"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d49f9d4bdf56"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_key", sa.String(length=300), nullable=False),
        sa.Column("nit", sa.String(length=15), nullable=True),
        sa.Column("verification_digit", sa.String(length=1), nullable=True),
        sa.Column("legal_name", sa.String(length=1000), nullable=False),
        sa.Column("normalized_name", sa.String(length=1000), nullable=False),
        sa.Column("legal_form", sa.String(length=300), nullable=True),
        sa.Column("registration_status", sa.String(length=100), nullable=True),
        sa.Column("primary_ciiu", sa.String(length=20), nullable=True),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.Column("municipality", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_key"),
    )
    op.create_index(op.f("ix_companies_nit"), "companies", ["nit"], unique=False)
    op.create_index(
        op.f("ix_companies_normalized_name"), "companies", ["normalized_name"], unique=False
    )
    op.create_index(
        "ix_companies_name_prefix",
        "companies",
        ["normalized_name"],
        postgresql_ops={"normalized_name": "text_pattern_ops"},
    )
    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("provider", sa.String(length=300), nullable=False),
        sa.Column("dataset_url", sa.String(length=1000), nullable=False),
        sa.Column("api_url", sa.String(length=1000), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("availability", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "company_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=1000), nullable=False),
        sa.Column("normalized_name", sa.String(length=1000), nullable=False),
        sa.Column("alias_type", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["data_sources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "normalized_name", "alias_type"),
    )
    op.create_index(
        op.f("ix_company_aliases_company_id"), "company_aliases", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_company_aliases_normalized_name"),
        "company_aliases",
        ["normalized_name"],
        unique=False,
    )
    op.create_index(
        "ix_aliases_name_prefix",
        "company_aliases",
        ["normalized_name"],
        postgresql_ops={"normalized_name": "text_pattern_ops"},
    )
    op.create_table(
        "source_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("external_record_id", sa.String(length=300), nullable=True),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("source_nit", sa.String(length=100), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["data_sources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_record_id", "payload_hash"),
    )
    op.create_index(
        "ix_source_records_company_retrieved",
        "source_records",
        ["company_id", "retrieved_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_source_records_company_retrieved", table_name="source_records")
    op.drop_table("source_records")
    op.drop_index(op.f("ix_company_aliases_normalized_name"), table_name="company_aliases")
    op.drop_index(op.f("ix_company_aliases_company_id"), table_name="company_aliases")
    op.drop_table("company_aliases")
    op.drop_table("data_sources")
    op.drop_index(op.f("ix_companies_normalized_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_nit"), table_name="companies")
    op.drop_table("companies")
