"""Conversion and validation of Phase 1 chunks for retrieval indexes."""

from collections.abc import Sequence

from langchain_core.documents import Document
from pydantic import ValidationError

from financial_rag.core.errors import DuplicateChunkError, EmptyCorpusError, RetrievalError
from financial_rag.domain.metadata import ChunkMetadata
from financial_rag.domain.retrieval import ChunkRecord


def records_from_documents(documents: Sequence[Document]) -> tuple[ChunkRecord, ...]:
    """Validate LangChain chunks and preserve their complete metadata lineage."""
    if not documents:
        raise EmptyCorpusError("At least one Phase 1 chunk is required for indexing")

    records: list[ChunkRecord] = []
    for document in documents:
        if not document.page_content.strip():
            raise RetrievalError("Indexed chunk content cannot be blank")
        try:
            metadata = ChunkMetadata.model_validate(document.metadata)
        except ValidationError as exc:
            raise RetrievalError("Indexed chunk metadata is invalid") from exc
        records.append(ChunkRecord(content=document.page_content, metadata=metadata))

    return validate_records(records)


def validate_records(records: Sequence[ChunkRecord]) -> tuple[ChunkRecord, ...]:
    """Require a non-empty corpus with globally unique chunk identifiers."""
    if not records:
        raise EmptyCorpusError("At least one chunk record is required")
    chunk_ids = [record.metadata.chunk_id for record in records]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise DuplicateChunkError("Chunk IDs must be unique within an indexed corpus")
    return tuple(records)
