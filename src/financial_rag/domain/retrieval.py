"""Pydantic contracts for the platform_v1 retrieval layer."""

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from financial_rag.domain.fingerprints import ConfigurationFingerprint, fingerprint_model
from financial_rag.domain.metadata import ChunkMetadata


class RetrievalMode(StrEnum):
    """Supported controlled-comparison retrieval routes."""

    DENSE = "dense"
    HYBRID = "hybrid"
    HYBRID_RERANKED = "hybrid_reranked"


class AliasRule(BaseModel):
    """One deterministic finance query-expansion rule."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    alias: str = Field(min_length=1)
    expansions: tuple[str, ...] = Field(min_length=1)

    @field_validator("expansions")
    @classmethod
    def expansions_must_be_non_blank(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("query expansions cannot be blank")
        return values


class QueryExpansionConfig(BaseModel):
    """Versioned, immutable finance alias-map configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    version: str = Field(default="finance_aliases_v1", min_length=1)
    rules: tuple[AliasRule, ...] = ()

    @model_validator(mode="after")
    def aliases_must_be_unique(self) -> Self:
        aliases = [rule.alias.casefold() for rule in self.rules]
        if len(aliases) != len(set(aliases)):
            raise ValueError("query-expansion aliases must be unique")
        return self


class RetrievalConfig(BaseModel):
    """Frozen platform_v1 retrieval protocol configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_version: Literal["platform_v1"] = "platform_v1"
    embedding_model_identifier: str = "BAAI/bge-m3"
    embedding_dimension: int = Field(default=1024, gt=0)
    normalization_method: Literal["l2"] = "l2"
    dense_index_type: Literal["faiss_index_flat_ip"] = "faiss_index_flat_ip"
    bm25_k1: float = Field(default=1.5, gt=0)
    bm25_b: float = Field(default=0.75, ge=0, le=1)
    dense_candidate_count: int = Field(default=20, gt=0)
    bm25_candidate_count: int = Field(default=10, gt=0)
    rrf_k: int = Field(default=30, gt=0)
    dense_rrf_weight: float = Field(default=1.0, gt=0)
    bm25_rrf_weight: float = Field(default=0.2, gt=0)
    final_top_k: int = Field(default=10, gt=0)
    reranker_model_identifier: str = "BAAI/bge-reranker-v2-m3"
    query_expansion: QueryExpansionConfig = QueryExpansionConfig()

    @property
    def fingerprint(self) -> ConfigurationFingerprint:
        """Return the immutable fingerprint of every retrieval setting."""
        return fingerprint_model(self)

    @classmethod
    def from_json_file(cls, path: Path) -> Self:
        """Load a versioned non-secret configuration through pathlib."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unable to load retrieval configuration: {path}") from exc
        return cls.model_validate(payload)


class ChunkRecord(BaseModel):
    """Serializable alignment record for one indexed Phase 1 chunk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1)
    metadata: ChunkMetadata


class RetrievedChunk(ChunkMetadata):
    """Ranked chunk with full Phase 1 lineage and transparent score fields."""

    content: str = Field(min_length=1)
    rank: int = Field(ge=1)
    dense_rank: int | None = Field(default=None, ge=1)
    dense_score: float | None = None
    bm25_rank: int | None = Field(default=None, ge=1)
    bm25_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class RetrievalResult(BaseModel):
    """Ranked output from one platform_v1 retrieval route."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=1)
    expanded_query: str = Field(min_length=1)
    mode: RetrievalMode
    document_unknown: Literal[True] = True
    retrieval_configuration_fingerprint: ConfigurationFingerprint
    chunks: tuple[RetrievedChunk, ...]

    @model_validator(mode="after")
    def ranks_must_be_contiguous(self) -> Self:
        expected = list(range(1, len(self.chunks) + 1))
        if [chunk.rank for chunk in self.chunks] != expected:
            raise ValueError("retrieved chunk ranks must be contiguous and one-based")
        return self


class EmbeddingIndexManifest(BaseModel):
    """Compatibility contract for local FAISS and chunk-mapping artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_version: Literal["platform_v1"] = "platform_v1"
    embedding_model_identifier: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    normalization_method: str = Field(default="l2", min_length=1)
    chunking_configuration_fingerprint: ConfigurationFingerprint
    chunk_mapping_fingerprint: ConfigurationFingerprint
    index_vector_fingerprint: ConfigurationFingerprint
    corpus_chunk_count: int = Field(gt=0)
    retrieval_configuration_fingerprint: ConfigurationFingerprint
    creation_timestamp: datetime
    artifact_format_version: Literal["faiss-flatip-v1"] = "faiss-flatip-v1"

    @field_validator("creation_timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("creation_timestamp must be timezone-aware")
        return value
