"""PostgreSQL schema mapping tests that require no running database."""

from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from financial_rag.storage.models import EMBEDDING_DIMENSION, Base, ChunkEmbeddingRow


def test_expected_revision_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "documents",
        "chunks",
        "corpus_revisions",
        "corpus_revision_documents",
        "corpus_revision_chunks",
        "index_revisions",
        "chunk_embeddings",
        "corpus_build_jobs",
    }


def test_embedding_column_is_fixed_dimension_pgvector() -> None:
    column_type = ChunkEmbeddingRow.__table__.c.embedding.type

    assert isinstance(column_type, VECTOR)
    assert column_type.dim == EMBEDDING_DIMENSION == 1024


def test_all_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    ddl = "\n".join(
        str(CreateTable(table).compile(dialect=dialect)) for table in Base.metadata.sorted_tables
    )

    assert "VECTOR(1024)" in ddl
    assert "FOREIGN KEY(index_revision_id, corpus_revision_id)" in ddl
    assert "FOREIGN KEY(corpus_revision_id, chunk_id)" in ddl
