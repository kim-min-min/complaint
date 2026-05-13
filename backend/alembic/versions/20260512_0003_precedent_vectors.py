"""precedent vectors

Revision ID: 20260512_0003
Revises: 20260511_0002
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260512_0003"
down_revision: Union[str, None] = "20260511_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "precedents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("case_number", sa.String(length=120), nullable=False),
        sa.Column("case_name", sa.String(length=500), nullable=False),
        sa.Column("court_name", sa.String(length=160), nullable=True),
        sa.Column("verdict_date", sa.String(length=40), nullable=True),
        sa.Column("verdict_type", sa.String(length=120), nullable=True),
        sa.Column("case_type", sa.String(length=80), nullable=True),
        sa.Column("charges", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("holding", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("fact_context", sa.Text(), nullable=True),
        sa.Column("refs_articles", sa.Text(), nullable=True),
        sa.Column("refs_cases", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rag_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id"),
    )
    op.create_index(op.f("ix_precedents_id"), "precedents", ["id"], unique=False)
    op.create_index(op.f("ix_precedents_source_id"), "precedents", ["source_id"], unique=True)
    op.create_index(op.f("ix_precedents_category"), "precedents", ["category"], unique=False)
    op.create_index(op.f("ix_precedents_case_number"), "precedents", ["case_number"], unique=False)

    op.create_table(
        "precedent_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("precedent_id", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["precedent_id"], ["precedents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("ALTER TABLE precedent_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    op.create_index(op.f("ix_precedent_chunks_id"), "precedent_chunks", ["id"], unique=False)
    op.create_index(op.f("ix_precedent_chunks_precedent_id"), "precedent_chunks", ["precedent_id"], unique=False)
    op.create_index(op.f("ix_precedent_chunks_chunk_type"), "precedent_chunks", ["chunk_type"], unique=False)
    op.create_index(
        "ix_precedent_chunks_embedding_hnsw",
        "precedent_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_precedent_chunks_embedding_hnsw", table_name="precedent_chunks")
    op.drop_index(op.f("ix_precedent_chunks_chunk_type"), table_name="precedent_chunks")
    op.drop_index(op.f("ix_precedent_chunks_precedent_id"), table_name="precedent_chunks")
    op.drop_index(op.f("ix_precedent_chunks_id"), table_name="precedent_chunks")
    op.drop_table("precedent_chunks")

    op.drop_index(op.f("ix_precedents_case_number"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_category"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_source_id"), table_name="precedents")
    op.drop_index(op.f("ix_precedents_id"), table_name="precedents")
    op.drop_table("precedents")
