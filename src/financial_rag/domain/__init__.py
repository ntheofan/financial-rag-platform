"""Validated domain contracts for ingestion and chunking."""

from financial_rag.domain.chunking import DEFAULT_SEPARATORS, ChunkingConfig
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.identifiers import make_chunk_id, make_document_id
from financial_rag.domain.indexing import (
    ActiveIndexSelection,
    CorpusBuildJob,
    CorpusBuildJobId,
    CorpusBuildStatus,
    UploadDocument,
    make_corpus_build_job_id,
)
from financial_rag.domain.metadata import ChunkMetadata, DocumentMetadata, SourceMetadata
from financial_rag.domain.retrieval import (
    AliasRule,
    ChunkRecord,
    EmbeddingIndexManifest,
    QueryExpansionConfig,
    RetrievalConfig,
    RetrievalMode,
    RetrievalResult,
    RetrievedChunk,
)
from financial_rag.domain.revisions import (
    CorpusRevision,
    CorpusRevisionId,
    IndexRevision,
    IndexRevisionId,
    make_corpus_revision_id,
    make_index_revision_id,
)

__all__ = [
    "DEFAULT_SEPARATORS",
    "ActiveIndexSelection",
    "AliasRule",
    "ChunkMetadata",
    "ChunkRecord",
    "ChunkingConfig",
    "ConfigurationFingerprint",
    "CorpusBuildJob",
    "CorpusBuildJobId",
    "CorpusBuildStatus",
    "CorpusRevision",
    "CorpusRevisionId",
    "DocumentMetadata",
    "EmbeddingIndexManifest",
    "IndexRevision",
    "IndexRevisionId",
    "QueryExpansionConfig",
    "RetrievalConfig",
    "RetrievalMode",
    "RetrievalResult",
    "RetrievedChunk",
    "SourceMetadata",
    "UploadDocument",
    "make_chunk_id",
    "make_corpus_build_job_id",
    "make_corpus_revision_id",
    "make_document_id",
    "make_index_revision_id",
]
