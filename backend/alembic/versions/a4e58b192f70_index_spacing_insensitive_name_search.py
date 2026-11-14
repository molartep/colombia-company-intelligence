"""Index search-only names without spaces; preserve all company and alias data."""

import sqlalchemy as sa

from alembic import op

revision = "a4e58b192f70"
down_revision = "d49f9d4bdf56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_companies_compact_name_prefix",
        "companies",
        [
            sa.func.replace(
                sa.column("normalized_name"), sa.literal_column("' '"), sa.literal_column("''")
            ).label("compact_name")
        ],
        postgresql_ops={"compact_name": "text_pattern_ops"},
    )
    op.create_index(
        "ix_aliases_compact_name_prefix",
        "company_aliases",
        [
            sa.func.replace(
                sa.column("normalized_name"), sa.literal_column("' '"), sa.literal_column("''")
            ).label("compact_name")
        ],
        postgresql_ops={"compact_name": "text_pattern_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_aliases_compact_name_prefix", table_name="company_aliases")
    op.drop_index("ix_companies_compact_name_prefix", table_name="companies")
