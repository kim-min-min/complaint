"""precedent v2 fields

Revision ID: 20260613_0005
Revises: 20260512_0004
Create Date: 2026-06-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0005"
down_revision: Union[str, None] = "20260512_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("precedents", sa.Column("source_url", sa.String(length=500), nullable=True))
    op.add_column("precedents", sa.Column("primary_charge", sa.String(length=120), nullable=True))
    op.add_column("precedents", sa.Column("court_level", sa.String(length=40), nullable=True))
    op.add_column("precedents", sa.Column("reasoning_excerpt", sa.Text(), nullable=True))
    op.add_column(
        "precedents",
        sa.Column(
            "extraction_quality",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(op.f("ix_precedents_primary_charge"), "precedents", ["primary_charge"], unique=False)
    op.create_index(
        "ix_precedents_charges_gin",
        "precedents",
        ["charges"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_precedents_charges_gin", table_name="precedents")
    op.drop_index(op.f("ix_precedents_primary_charge"), table_name="precedents")
    op.drop_column("precedents", "extraction_quality")
    op.drop_column("precedents", "reasoning_excerpt")
    op.drop_column("precedents", "court_level")
    op.drop_column("precedents", "primary_charge")
    op.drop_column("precedents", "source_url")
