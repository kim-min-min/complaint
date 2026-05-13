"""primary case name

Revision ID: 20260512_0004
Revises: 20260512_0003
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_0004"
down_revision: Union[str, None] = "20260512_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("precedents", sa.Column("primary_case_name", sa.String(length=200), nullable=True))
    op.create_index(op.f("ix_precedents_primary_case_name"), "precedents", ["primary_case_name"], unique=False)
    op.execute(
        """
        UPDATE precedents
        SET primary_case_name = trim(split_part(case_name, '·', 1))
        WHERE primary_case_name IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_precedents_primary_case_name"), table_name="precedents")
    op.drop_column("precedents", "primary_case_name")
