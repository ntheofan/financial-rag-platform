"""Local save/load adapter for ignored FAISS, mapping, and manifest artifacts."""

import json
from pathlib import Path
from typing import Any, Literal

import faiss
from pydantic import BaseModel, ConfigDict, ValidationError

from financial_rag.core.errors import RetrievalArtifactError
from financial_rag.domain.fingerprints import ConfigurationFingerprint
from financial_rag.domain.retrieval import ChunkRecord, EmbeddingIndexManifest, RetrievalConfig
from financial_rag.retrieval.dense import DenseIndex
from financial_rag.retrieval.manifests import (
    fingerprint_chunk_mapping,
    validate_manifest_compatibility,
)

INDEX_FILENAME = "index.faiss"
MAPPING_FILENAME = "chunks.retrieval.json"
MANIFEST_FILENAME = "manifest.retrieval.json"


class _ChunkMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal["chunk-mapping-v1"] = "chunk-mapping-v1"
    chunks: tuple[ChunkRecord, ...]


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary_path.replace(path)


class DenseIndexArtifactStore:
    """Persist and restore a FAISS index with its exact chunk-row mapping."""

    def save(
        self,
        directory: Path,
        *,
        dense_index: DenseIndex,
        manifest: EmbeddingIndexManifest,
    ) -> None:
        """Write aligned artifacts under an explicit caller-owned pathlib path."""
        if manifest.corpus_chunk_count != dense_index.count:
            raise RetrievalArtifactError("Manifest count does not match the dense index")
        if manifest.embedding_dimension != dense_index.dimension:
            raise RetrievalArtifactError("Manifest dimension does not match the dense index")
        directory.mkdir(parents=True, exist_ok=True)
        index_path = directory / INDEX_FILENAME
        temporary_index_path = index_path.with_suffix(".tmp.faiss")
        try:
            faiss.write_index(dense_index.raw_index, str(temporary_index_path))
            temporary_index_path.replace(index_path)
            mapping = _ChunkMapping(chunks=dense_index.records)
            _write_json_atomic(
                directory / MAPPING_FILENAME,
                mapping.model_dump(mode="json"),
            )
            _write_json_atomic(
                directory / MANIFEST_FILENAME,
                manifest.model_dump(mode="json"),
            )
        except OSError as exc:
            raise RetrievalArtifactError(f"Unable to save retrieval artifacts: {exc}") from exc

    def load(
        self,
        directory: Path,
        *,
        config: RetrievalConfig,
        chunking_configuration_fingerprint: ConfigurationFingerprint,
    ) -> tuple[DenseIndex, EmbeddingIndexManifest]:
        """Load artifacts only after strict manifest and row-alignment validation."""
        index_path = directory / INDEX_FILENAME
        mapping_path = directory / MAPPING_FILENAME
        manifest_path = directory / MANIFEST_FILENAME
        if not all(path.is_file() for path in (index_path, mapping_path, manifest_path)):
            raise RetrievalArtifactError(f"Retrieval artifact set is incomplete: {directory}")
        try:
            manifest = EmbeddingIndexManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            validate_manifest_compatibility(
                manifest,
                config=config,
                chunking_configuration_fingerprint=chunking_configuration_fingerprint,
            )
            mapping = _ChunkMapping.model_validate_json(mapping_path.read_text(encoding="utf-8"))
            if fingerprint_chunk_mapping(mapping.chunks) != manifest.chunk_mapping_fingerprint:
                raise RetrievalArtifactError("Chunk mapping fingerprint does not match manifest")
            index: Any = faiss.read_index(str(index_path))
            dense_index = DenseIndex(
                index,
                mapping.chunks,
                dimension=manifest.embedding_dimension,
            )
            if dense_index.vector_fingerprint != manifest.index_vector_fingerprint:
                raise RetrievalArtifactError("FAISS vector fingerprint does not match manifest")
        except (OSError, ValueError, ValidationError, RuntimeError) as exc:
            if isinstance(exc, RetrievalArtifactError):
                raise
            raise RetrievalArtifactError(f"Unable to load retrieval artifacts: {exc}") from exc
        if dense_index.count != manifest.corpus_chunk_count:
            raise RetrievalArtifactError("Loaded index count does not match its manifest")
        return dense_index, manifest
