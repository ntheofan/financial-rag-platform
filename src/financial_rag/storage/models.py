"""SQLAlchemy 2 mappings for documents, chunks, and immutable revisions."""

from datetime import date, datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSION = 1024


class Base(DeclarativeBase):
    """Declarative base exported to Alembic."""


class DocumentRow(Base):
    """One content-derived Phase 1 source document."""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str | None] = mapped_column(Text)
    filing_type: Mapped[str | None] = mapped_column(String(64))
    filing_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChunkRow(Base):
    """One globally identified chunk with complete source lineage."""

    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index_nonnegative"),
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_chunks_page_number_positive",
        ),
        Index("ix_chunks_document_id", "document_id"),
    )

    chunk_id: Mapped[str] = mapped_column(String(38), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_heading: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CorpusRevisionRow(Base):
    """Immutable ordered corpus snapshot."""

    __tablename__ = "corpus_revisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'failed', 'archived')",
            name="ck_corpus_revisions_status",
        ),
        CheckConstraint("document_count > 0", name="ck_corpus_revisions_document_count"),
        CheckConstraint("chunk_count > 0", name="ck_corpus_revisions_chunk_count"),
    )

    corpus_revision_id: Mapped[str] = mapped_column(String(39), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    chunking_configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_mapping_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CorpusRevisionDocumentRow(Base):
    """Document membership for a corpus revision."""

    __tablename__ = "corpus_revision_documents"

    corpus_revision_id: Mapped[str] = mapped_column(
        ForeignKey("corpus_revisions.corpus_revision_id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="RESTRICT"), primary_key=True
    )


class CorpusRevisionChunkRow(Base):
    """Stable ordered chunk mapping for a corpus revision."""

    __tablename__ = "corpus_revision_chunks"
    __table_args__ = (
        UniqueConstraint(
            "corpus_revision_id",
            "position",
            name="uq_corpus_revision_chunks_position",
        ),
        CheckConstraint("position >= 0", name="ck_corpus_revision_chunks_position"),
    )

    corpus_revision_id: Mapped[str] = mapped_column(
        ForeignKey("corpus_revisions.corpus_revision_id", ondelete="CASCADE"),
        primary_key=True,
    )
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("chunks.chunk_id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class IndexRevisionRow(Base):
    """Compatibility metadata for one pgvector embedding revision."""

    __tablename__ = "index_revisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'failed', 'archived')",
            name="ck_index_revisions_status",
        ),
        CheckConstraint(
            f"embedding_dimension = {EMBEDDING_DIMENSION}",
            name="ck_index_revisions_embedding_dimension",
        ),
        CheckConstraint("vector_count > 0", name="ck_index_revisions_vector_count"),
        UniqueConstraint(
            "index_revision_id",
            "corpus_revision_id",
            name="uq_index_revisions_identity_corpus",
        ),
        Index("ix_index_revisions_corpus_revision_id", "corpus_revision_id"),
    )

    index_revision_id: Mapped[str] = mapped_column(String(38), primary_key=True)
    corpus_revision_id: Mapped[str] = mapped_column(
        ForeignKey("corpus_revisions.corpus_revision_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    embedding_model_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    normalization_method: Mapped[str] = mapped_column(String(32), nullable=False)
    chunk_mapping_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    index_vector_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    vector_count: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_format_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChunkEmbeddingRow(Base):
    """A vector row aligned to a chunk position in one index revision."""

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["index_revision_id", "corpus_revision_id"],
            ["index_revisions.index_revision_id", "index_revisions.corpus_revision_id"],
            ondelete="CASCADE",
            name="fk_chunk_embeddings_index_corpus",
        ),
        ForeignKeyConstraint(
            ["corpus_revision_id", "chunk_id"],
            ["corpus_revision_chunks.corpus_revision_id", "corpus_revision_chunks.chunk_id"],
            ondelete="RESTRICT",
            name="fk_chunk_embeddings_corpus_chunk",
        ),
        UniqueConstraint(
            "index_revision_id", "position", name="uq_chunk_embeddings_index_position"
        ),
        CheckConstraint("position >= 0", name="ck_chunk_embeddings_position"),
    )

    index_revision_id: Mapped[str] = mapped_column(String(38), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(38), primary_key=True)
    corpus_revision_id: Mapped[str] = mapped_column(String(39), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(EMBEDDING_DIMENSION), nullable=False)


class CorpusBuildJobRow(Base):
    """Privacy-minimized durable status for one local in-process build job."""

    __tablename__ = "corpus_build_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_corpus_build_jobs_status",
        ),
        CheckConstraint(
            "input_file_count BETWEEN 1 AND 10",
            name="ck_corpus_build_jobs_file_count",
        ),
        Index("ix_corpus_build_jobs_created_at", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    input_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    corpus_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("corpus_revisions.corpus_revision_id", ondelete="RESTRICT")
    )
    index_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("index_revisions.index_revision_id", ondelete="RESTRICT")
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
