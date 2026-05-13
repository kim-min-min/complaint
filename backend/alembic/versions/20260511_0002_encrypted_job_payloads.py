"""encrypted job payloads

Revision ID: 20260511_0002
Revises: 20260511_0001
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260511_0002"
down_revision: Union[str, None] = "20260511_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_column("complaints", "input_json")
    op.drop_column("complaints", "result_text")

    op.add_column("ai_jobs", sa.Column("encrypted_payload", sa.Text(), nullable=True))
    op.add_column("ai_jobs", sa.Column("encrypted_result", sa.Text(), nullable=True))
    op.add_column("ai_jobs", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_jobs", "expires_at")
    op.drop_column("ai_jobs", "encrypted_result")
    op.drop_column("ai_jobs", "encrypted_payload")

    op.add_column("complaints", sa.Column("result_text", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False))
    op.drop_column("complaints", "expires_at")
