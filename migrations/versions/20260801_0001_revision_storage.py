"""Create document, corpus revision, and pgvector index storage.

Revision ID: 20260801_0001
Revises: None
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision: str = "20260801_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install pgvector and create the initial immutable revision schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("filing_type", sa.String(length=64), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_table(
        "corpus_revisions",
        sa.Column("corpus_revision_id", sa.String(length=39), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("chunking_configuration_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("chunk_mapping_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ready', 'failed', 'archived')",
            name="ck_corpus_revisions_status",
        ),
        sa.CheckConstraint("document_count > 0", name="ck_corpus_revisions_document_count"),
        sa.CheckConstraint("chunk_count > 0", name="ck_corpus_revisions_chunk_count"),
        sa.PrimaryKeyConstraint("corpus_revision_id"),
    )
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(length=38), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_heading", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index_nonnegative"),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_chunks_page_number_positive",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"], unique=False)
    op.create_table(
        "corpus_revision_documents",
        sa.Column("corpus_revision_id", sa.String(length=39), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["corpus_revision_id"],
            ["corpus_revisions.corpus_revision_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("corpus_revision_id", "document_id"),
    )
    op.create_table(
        "corpus_revision_chunks",
        sa.Column("corpus_revision_id", sa.String(length=39), nullable=False),
        sa.Column("chunk_id", sa.String(length=38), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_corpus_revision_chunks_position"),
        sa.ForeignKeyConstraint(
            ["corpus_revision_id"],
            ["corpus_revisions.corpus_revision_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.chunk_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("corpus_revision_id", "chunk_id"),
        sa.UniqueConstraint(
            "corpus_revision_id",
            "position",
            name="uq_corpus_revision_chunks_position",
        ),
    )
    op.create_table(
        "index_revisions",
        sa.Column("index_revision_id", sa.String(length=38), nullable=False),
        sa.Column("corpus_revision_id", sa.String(length=39), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("embedding_model_identifier", sa.Text(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("normalization_method", sa.String(length=32), nullable=False),
        sa.Column("chunk_mapping_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("index_vector_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("retrieval_configuration_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("vector_count", sa.Integer(), nullable=False),
        sa.Column("artifact_format_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ready', 'failed', 'archived')", name="ck_index_revisions_status"
        ),
        sa.CheckConstraint(
            "embedding_dimension = 1024", name="ck_index_revisions_embedding_dimension"
        ),
        sa.CheckConstraint("vector_count > 0", name="ck_index_revisions_vector_count"),
        sa.ForeignKeyConstraint(
            ["corpus_revision_id"],
            ["corpus_revisions.corpus_revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("index_revision_id"),
        sa.UniqueConstraint(
            "index_revision_id",
            "corpus_revision_id",
            name="uq_index_revisions_identity_corpus",
        ),
    )
    op.create_index(
        "ix_index_revisions_corpus_revision_id",
        "index_revisions",
        ["corpus_revision_id"],
        unique=False,
    )
    op.create_table(
        "chunk_embeddings",
        sa.Column("index_revision_id", sa.String(length=38), nullable=False),
        sa.Column("chunk_id", sa.String(length=38), nullable=False),
        sa.Column("corpus_revision_id", sa.String(length=39), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("embedding", VECTOR(dim=1024), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_chunk_embeddings_position"),
        sa.ForeignKeyConstraint(
            ["corpus_revision_id", "chunk_id"],
            [
                "corpus_revision_chunks.corpus_revision_id",
                "corpus_revision_chunks.chunk_id",
            ],
            name="fk_chunk_embeddings_corpus_chunk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["index_revision_id", "corpus_revision_id"],
            ["index_revisions.index_revision_id", "index_revisions.corpus_revision_id"],
            name="fk_chunk_embeddings_index_corpus",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("index_revision_id", "chunk_id"),
        sa.UniqueConstraint(
            "index_revision_id", "position", name="uq_chunk_embeddings_index_position"
        ),
    )


def downgrade() -> None:
    """Remove project-owned tables while leaving the shared vector extension installed."""
    op.drop_table("chunk_embeddings")
    op.drop_index("ix_index_revisions_corpus_revision_id", table_name="index_revisions")
    op.drop_table("index_revisions")
    op.drop_table("corpus_revision_chunks")
    op.drop_table("corpus_revision_documents")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("corpus_revisions")
    op.drop_table("documents")
