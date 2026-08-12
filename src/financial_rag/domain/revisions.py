"""Immutable contracts and deterministic identities for persisted revisions."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from financial_rag.domain.fingerprints import ConfigurationFingerprint, fingerprint_payload
from financial_rag.domain.retrieval import ChunkRecord, EmbeddingIndexManifest

CorpusRevisionId = Annotated[str, Field(pattern=r"^corpus_[0-9a-f]{32}$")]
IndexRevisionId = Annotated[str, Field(pattern=r"^index_[0-9a-f]{32}$")]
RevisionStatus = Literal["ready", "failed", "archived"]


def make_corpus_revision_id(
    records: tuple[ChunkRecord, ...],
    *,
    chunking_configuration_fingerprint: ConfigurationFingerprint,
) -> CorpusRevisionId:
    """Identify one ordered corpus and its chunking semantics deterministically."""
    fingerprint = fingerprint_payload(
        {
            "chunking_configuration_fingerprint": chunking_configuration_fingerprint.model_dump(
                mode="json"
            ),
            "records": [record.model_dump(mode="json") for record in records],
        }
    )
    return f"corpus_{fingerprint.value[:32]}"


def make_index_revision_id(
    corpus_revision_id: CorpusRevisionId,
    *,
    manifest: EmbeddingIndexManifest,
) -> IndexRevisionId:
    """Identify an embedding revision independently of its creation timestamp."""
    manifest_identity = manifest.model_dump(mode="json", exclude={"creation_timestamp"})
    fingerprint = fingerprint_payload(
        {"corpus_revision_id": corpus_revision_id, "manifest": manifest_identity}
    )
    return f"index_{fingerprint.value[:32]}"


class CorpusRevision(BaseModel):
    """Durable identity and compatibility metadata for an ordered chunk corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_revision_id: CorpusRevisionId
    status: RevisionStatus
    label: str | None = Field(default=None, max_length=200)
    chunking_configuration_fingerprint: ConfigurationFingerprint
    chunk_mapping_fingerprint: ConfigurationFingerprint
    document_count: int = Field(gt=0)
    chunk_count: int = Field(gt=0)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class IndexRevision(BaseModel):
    """Durable identity and compatibility metadata for one embedding matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index_revision_id: IndexRevisionId
    corpus_revision_id: CorpusRevisionId
    status: RevisionStatus
    embedding_model_identifier: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    normalization_method: str = Field(min_length=1)
    chunk_mapping_fingerprint: ConfigurationFingerprint
    index_vector_fingerprint: ConfigurationFingerprint
    retrieval_configuration_fingerprint: ConfigurationFingerprint
    vector_count: int = Field(gt=0)
    artifact_format_version: str = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value
