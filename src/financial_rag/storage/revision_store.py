"""Transactional PostgreSQL store for immutable corpus and index revisions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import numpy as np
import structlog
from numpy.typing import ArrayLike, NDArray
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financial_rag.core.errors import (
    RevisionCompatibilityError,
    RevisionConflictError,
    RevisionNotFoundError,
)
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.metadata import ChunkMetadata
from financial_rag.domain.retrieval import ChunkRecord, EmbeddingIndexManifest
from financial_rag.domain.revisions import (
    CorpusRevision,
    CorpusRevisionId,
    IndexRevision,
    IndexRevisionId,
    RevisionStatus,
    make_corpus_revision_id,
    make_index_revision_id,
)
from financial_rag.retrieval.corpus import validate_records
from financial_rag.retrieval.manifests import fingerprint_chunk_mapping
from financial_rag.retrieval.vectors import fingerprint_vector_matrix, normalize_l2
from financial_rag.storage.models import (
    EMBEDDING_DIMENSION,
    ChunkEmbeddingRow,
    ChunkRow,
    CorpusRevisionChunkRow,
    CorpusRevisionDocumentRow,
    CorpusRevisionRow,
    DocumentRow,
    IndexRevisionRow,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PersistedIndex:
    """Loaded aligned records and vectors for a durable index revision."""

    revision: IndexRevision
    records: tuple[ChunkRecord, ...]
    embeddings: NDArray[np.float32]


def _fingerprint(value: str) -> ConfigurationFingerprint:
    return ConfigurationFingerprint(value=value)


def _aware(value: datetime) -> datetime:
    """Defensively interpret naive driver timestamps as UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _corpus_contract(row: CorpusRevisionRow) -> CorpusRevision:
    return CorpusRevision(
        corpus_revision_id=row.corpus_revision_id,
        status=cast(RevisionStatus, row.status),
        label=row.label,
        chunking_configuration_fingerprint=_fingerprint(row.chunking_configuration_fingerprint),
        chunk_mapping_fingerprint=_fingerprint(row.chunk_mapping_fingerprint),
        document_count=row.document_count,
        chunk_count=row.chunk_count,
        created_at=_aware(row.created_at),
    )


def _index_contract(row: IndexRevisionRow) -> IndexRevision:
    return IndexRevision(
        index_revision_id=row.index_revision_id,
        corpus_revision_id=row.corpus_revision_id,
        status=cast(RevisionStatus, row.status),
        embedding_model_identifier=row.embedding_model_identifier,
        embedding_dimension=row.embedding_dimension,
        normalization_method=row.normalization_method,
        chunk_mapping_fingerprint=_fingerprint(row.chunk_mapping_fingerprint),
        index_vector_fingerprint=_fingerprint(row.index_vector_fingerprint),
        retrieval_configuration_fingerprint=_fingerprint(row.retrieval_configuration_fingerprint),
        vector_count=row.vector_count,
        artifact_format_version=row.artifact_format_version,
        created_at=_aware(row.created_at),
    )


def _document_values(record: ChunkRecord) -> tuple[object, ...]:
    metadata = record.metadata
    return (
        metadata.source_file,
        metadata.company,
        metadata.filing_type,
        metadata.filing_date,
    )


def _chunk_values(record: ChunkRecord) -> tuple[object, ...]:
    metadata = record.metadata
    return (
        metadata.document_id,
        record.content,
        metadata.chunk_index,
        metadata.page_number,
        metadata.section_heading,
    )


class PostgresRevisionStore:
    """Persist and load complete revisions using caller-configured async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def persist_corpus(
        self,
        records: tuple[ChunkRecord, ...],
        *,
        chunking_configuration_fingerprint: ConfigurationFingerprint,
        label: str | None = None,
    ) -> CorpusRevision:
        """Atomically persist an ordered corpus, returning an existing identical revision."""
        validated = validate_records(records)
        revision_id = make_corpus_revision_id(
            validated,
            chunking_configuration_fingerprint=chunking_configuration_fingerprint,
        )
        mapping_fingerprint = fingerprint_chunk_mapping(validated)
        created_at = datetime.now(UTC)
        try:
            async with self._session_factory() as session, session.begin():
                existing = await session.get(CorpusRevisionRow, revision_id)
                if existing is not None:
                    existing_contract, existing_records = await self._load_corpus(
                        session, revision_id
                    )
                    if existing_records != validated:
                        raise RevisionConflictError(
                            f"Corpus revision identity collision: {revision_id}"
                        )
                    return existing_contract

                document_ids: set[str] = set()
                document_records: dict[str, ChunkRecord] = {}
                for record in validated:
                    metadata = record.metadata
                    document_ids.add(metadata.document_id)
                    prior_record = document_records.get(metadata.document_id)
                    if prior_record is not None:
                        if _document_values(prior_record) != _document_values(record):
                            raise RevisionConflictError(
                                "One corpus supplies conflicting metadata for document: "
                                f"{metadata.document_id}"
                            )
                        continue
                    document_records[metadata.document_id] = record
                    document = await session.get(DocumentRow, metadata.document_id)
                    if document is None:
                        session.add(
                            DocumentRow(
                                document_id=metadata.document_id,
                                source_file=metadata.source_file,
                                company=metadata.company,
                                filing_type=metadata.filing_type,
                                filing_date=metadata.filing_date,
                                created_at=created_at,
                            )
                        )
                    elif (
                        document.source_file,
                        document.company,
                        document.filing_type,
                        document.filing_date,
                    ) != _document_values(record):
                        raise RevisionConflictError(
                            f"Document identity has conflicting metadata: {metadata.document_id}"
                        )

                for record in validated:
                    metadata = record.metadata
                    chunk = await session.get(ChunkRow, metadata.chunk_id)
                    if chunk is None:
                        session.add(
                            ChunkRow(
                                chunk_id=metadata.chunk_id,
                                document_id=metadata.document_id,
                                content=record.content,
                                chunk_index=metadata.chunk_index,
                                page_number=metadata.page_number,
                                section_heading=metadata.section_heading,
                                created_at=created_at,
                            )
                        )
                    elif (
                        chunk.document_id,
                        chunk.content,
                        chunk.chunk_index,
                        chunk.page_number,
                        chunk.section_heading,
                    ) != _chunk_values(record):
                        raise RevisionConflictError(
                            "Chunk identity has conflicting content or lineage: "
                            f"{metadata.chunk_id}"
                        )

                row = CorpusRevisionRow(
                    corpus_revision_id=revision_id,
                    status="ready",
                    label=label,
                    chunking_configuration_fingerprint=(chunking_configuration_fingerprint.value),
                    chunk_mapping_fingerprint=mapping_fingerprint.value,
                    document_count=len(document_ids),
                    chunk_count=len(validated),
                    created_at=created_at,
                )
                session.add(row)
                await session.flush()
                session.add_all(
                    CorpusRevisionDocumentRow(
                        corpus_revision_id=revision_id, document_id=document_id
                    )
                    for document_id in sorted(document_ids)
                )
                session.add_all(
                    CorpusRevisionChunkRow(
                        corpus_revision_id=revision_id,
                        chunk_id=record.metadata.chunk_id,
                        position=position,
                    )
                    for position, record in enumerate(validated)
                )
                await session.flush()
                result = _corpus_contract(row)
        except IntegrityError as exc:
            raise RevisionConflictError(
                f"Concurrent or conflicting corpus revision: {revision_id}"
            ) from exc
        logger.info(
            "corpus_revision_persisted",
            corpus_revision_id=revision_id,
            document_count=result.document_count,
            chunk_count=result.chunk_count,
        )
        return result

    async def get_corpus(
        self, corpus_revision_id: CorpusRevisionId
    ) -> tuple[CorpusRevision, tuple[ChunkRecord, ...]]:
        """Load a revision and reconstruct its exact ordered Phase 2 mapping."""
        async with self._session_factory() as session:
            return await self._load_corpus(session, corpus_revision_id)

    async def get_corpus_revision(self, corpus_revision_id: CorpusRevisionId) -> CorpusRevision:
        """Load only corpus compatibility metadata for control-plane callers."""
        async with self._session_factory() as session:
            row = await session.get(CorpusRevisionRow, corpus_revision_id)
            if row is None:
                raise RevisionNotFoundError(f"Corpus revision not found: {corpus_revision_id}")
            return _corpus_contract(row)

    async def list_corpus_revisions(self, *, limit: int = 50) -> tuple[CorpusRevision, ...]:
        """List recent corpus metadata without loading stored chunk content."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = (
            select(CorpusRevisionRow)
            .order_by(CorpusRevisionRow.created_at.desc(), CorpusRevisionRow.corpus_revision_id)
            .limit(limit)
        )
        async with self._session_factory() as session:
            return tuple(_corpus_contract(row) for row in await session.scalars(statement))

    async def persist_index(
        self,
        corpus_revision_id: CorpusRevisionId,
        *,
        records: tuple[ChunkRecord, ...],
        embeddings: ArrayLike,
        manifest: EmbeddingIndexManifest,
    ) -> IndexRevision:
        """Atomically persist a validated Phase 2 manifest and aligned vectors."""
        validated = validate_records(records)
        if manifest.embedding_dimension != EMBEDDING_DIMENSION:
            raise RevisionCompatibilityError(
                f"pgvector schema requires {EMBEDDING_DIMENSION}-dimensional embeddings"
            )
        matrix = normalize_l2(embeddings, dimension=manifest.embedding_dimension)
        if matrix.shape[0] != len(validated):
            raise RevisionCompatibilityError("Embedding rows and chunk records are not aligned")
        mapping_fingerprint = fingerprint_chunk_mapping(validated)
        vector_fingerprint = fingerprint_vector_matrix(
            matrix, dimension=manifest.embedding_dimension
        )
        if manifest.corpus_chunk_count != len(validated):
            raise RevisionCompatibilityError("Manifest chunk count does not match records")
        if manifest.chunk_mapping_fingerprint != mapping_fingerprint:
            raise RevisionCompatibilityError("Manifest chunk mapping does not match records")
        if manifest.index_vector_fingerprint != vector_fingerprint:
            raise RevisionCompatibilityError("Manifest vector fingerprint does not match vectors")

        revision_id = make_index_revision_id(corpus_revision_id, manifest=manifest)
        try:
            async with self._session_factory() as session, session.begin():
                corpus, stored_records = await self._load_corpus(session, corpus_revision_id)
                if stored_records != validated:
                    raise RevisionCompatibilityError(
                        "Index records do not match the persisted corpus revision"
                    )
                if corpus.chunk_mapping_fingerprint != mapping_fingerprint:
                    raise RevisionCompatibilityError(
                        "Index mapping fingerprint does not match the corpus revision"
                    )
                if (
                    corpus.chunking_configuration_fingerprint
                    != manifest.chunking_configuration_fingerprint
                ):
                    raise RevisionCompatibilityError(
                        "Index manifest chunking fingerprint does not match the corpus revision"
                    )
                if corpus.status != "ready":
                    raise RevisionCompatibilityError("Only ready corpus revisions can be indexed")
                existing = await session.get(IndexRevisionRow, revision_id)
                if existing is not None:
                    return _index_contract(existing)

                row = IndexRevisionRow(
                    index_revision_id=revision_id,
                    corpus_revision_id=corpus_revision_id,
                    status="ready",
                    embedding_model_identifier=manifest.embedding_model_identifier,
                    embedding_dimension=manifest.embedding_dimension,
                    normalization_method=manifest.normalization_method,
                    chunk_mapping_fingerprint=manifest.chunk_mapping_fingerprint.value,
                    index_vector_fingerprint=manifest.index_vector_fingerprint.value,
                    retrieval_configuration_fingerprint=(
                        manifest.retrieval_configuration_fingerprint.value
                    ),
                    vector_count=len(validated),
                    artifact_format_version=manifest.artifact_format_version,
                    created_at=manifest.creation_timestamp,
                )
                session.add(row)
                await session.flush()
                session.add_all(
                    ChunkEmbeddingRow(
                        index_revision_id=revision_id,
                        corpus_revision_id=corpus_revision_id,
                        chunk_id=record.metadata.chunk_id,
                        position=position,
                        embedding=matrix[position].tolist(),
                    )
                    for position, record in enumerate(validated)
                )
                await session.flush()
                result = _index_contract(row)
        except IntegrityError as exc:
            raise RevisionConflictError(
                f"Concurrent or conflicting index revision: {revision_id}"
            ) from exc
        logger.info(
            "index_revision_persisted",
            index_revision_id=revision_id,
            corpus_revision_id=corpus_revision_id,
            vector_count=result.vector_count,
        )
        return result

    async def get_index(self, index_revision_id: IndexRevisionId) -> PersistedIndex:
        """Load and revalidate the exact ordered vectors for one index revision."""
        async with self._session_factory() as session:
            row = await session.get(IndexRevisionRow, index_revision_id)
            if row is None:
                raise RevisionNotFoundError(f"Index revision not found: {index_revision_id}")
            revision = _index_contract(row)
            _, records = await self._load_corpus(session, revision.corpus_revision_id)
            statement = (
                select(ChunkEmbeddingRow)
                .where(ChunkEmbeddingRow.index_revision_id == index_revision_id)
                .order_by(ChunkEmbeddingRow.position)
            )
            vector_rows = tuple((await session.scalars(statement)).all())
            if len(vector_rows) != revision.vector_count:
                raise RevisionCompatibilityError("Persisted vector count does not match revision")
            if [item.chunk_id for item in vector_rows] != [
                record.metadata.chunk_id for record in records
            ]:
                raise RevisionCompatibilityError("Persisted vector rows are not chunk-aligned")
            matrix = normalize_l2(
                [item.embedding for item in vector_rows],
                dimension=revision.embedding_dimension,
            )
            if (
                fingerprint_vector_matrix(matrix, dimension=revision.embedding_dimension)
                != revision.index_vector_fingerprint
            ):
                raise RevisionCompatibilityError("Persisted vectors fail fingerprint validation")
            return PersistedIndex(revision=revision, records=records, embeddings=matrix)

    async def get_index_revision(self, index_revision_id: IndexRevisionId) -> IndexRevision:
        """Load only index compatibility metadata without reading vector rows."""
        async with self._session_factory() as session:
            row = await session.get(IndexRevisionRow, index_revision_id)
            if row is None:
                raise RevisionNotFoundError(f"Index revision not found: {index_revision_id}")
            return _index_contract(row)

    async def list_index_revisions(self, *, limit: int = 50) -> tuple[IndexRevision, ...]:
        """List recent index metadata without loading embedding vectors."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = (
            select(IndexRevisionRow)
            .order_by(IndexRevisionRow.created_at.desc(), IndexRevisionRow.index_revision_id)
            .limit(limit)
        )
        async with self._session_factory() as session:
            return tuple(_index_contract(row) for row in await session.scalars(statement))

    async def _load_corpus(
        self,
        session: AsyncSession,
        corpus_revision_id: CorpusRevisionId,
    ) -> tuple[CorpusRevision, tuple[ChunkRecord, ...]]:
        row = await session.get(CorpusRevisionRow, corpus_revision_id)
        if row is None:
            raise RevisionNotFoundError(f"Corpus revision not found: {corpus_revision_id}")
        statement = (
            select(CorpusRevisionChunkRow, ChunkRow, DocumentRow)
            .join(ChunkRow, ChunkRow.chunk_id == CorpusRevisionChunkRow.chunk_id)
            .join(DocumentRow, DocumentRow.document_id == ChunkRow.document_id)
            .where(CorpusRevisionChunkRow.corpus_revision_id == corpus_revision_id)
            .order_by(CorpusRevisionChunkRow.position)
        )
        records = tuple(
            ChunkRecord(
                content=chunk.content,
                metadata=ChunkMetadata(
                    document_id=document.document_id,
                    source_file=document.source_file,
                    company=document.company,
                    filing_type=document.filing_type,
                    filing_date=document.filing_date,
                    page_number=chunk.page_number,
                    section_heading=chunk.section_heading,
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                ),
            )
            for _, chunk, document in (await session.execute(statement)).all()
        )
        revision = _corpus_contract(row)
        if len(records) != revision.chunk_count:
            raise RevisionCompatibilityError("Persisted chunk count does not match revision")
        if fingerprint_chunk_mapping(records) != revision.chunk_mapping_fingerprint:
            raise RevisionCompatibilityError("Persisted corpus fails mapping validation")
        return revision, records
