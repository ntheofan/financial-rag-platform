"""Creation and compatibility validation for local dense-index manifests."""

from datetime import UTC, datetime

from financial_rag.core.errors import ManifestCompatibilityError
from financial_rag.domain.fingerprints import ConfigurationFingerprint, fingerprint_payload
from financial_rag.domain.retrieval import ChunkRecord, EmbeddingIndexManifest, RetrievalConfig


def fingerprint_chunk_mapping(
    records: tuple[ChunkRecord, ...],
) -> ConfigurationFingerprint:
    """Fingerprint ordered chunk IDs and content to protect FAISS row alignment."""
    return fingerprint_payload({"chunks": [record.model_dump(mode="json") for record in records]})


def create_index_manifest(
    *,
    config: RetrievalConfig,
    chunking_configuration_fingerprint: ConfigurationFingerprint,
    records: tuple[ChunkRecord, ...],
    index_vector_fingerprint: ConfigurationFingerprint,
    creation_timestamp: datetime | None = None,
) -> EmbeddingIndexManifest:
    """Build an immutable platform_v1 artifact manifest."""
    return EmbeddingIndexManifest(
        embedding_model_identifier=config.embedding_model_identifier,
        embedding_dimension=config.embedding_dimension,
        normalization_method=config.normalization_method,
        chunking_configuration_fingerprint=chunking_configuration_fingerprint,
        chunk_mapping_fingerprint=fingerprint_chunk_mapping(records),
        index_vector_fingerprint=index_vector_fingerprint,
        corpus_chunk_count=len(records),
        retrieval_configuration_fingerprint=config.fingerprint,
        creation_timestamp=creation_timestamp or datetime.now(UTC),
    )


def validate_manifest_compatibility(
    manifest: EmbeddingIndexManifest,
    *,
    config: RetrievalConfig,
    chunking_configuration_fingerprint: ConfigurationFingerprint,
) -> None:
    """Reject an index built with incompatible embedding or chunking semantics."""
    mismatches: list[str] = []
    if manifest.embedding_model_identifier != config.embedding_model_identifier:
        mismatches.append("embedding model")
    if manifest.embedding_dimension != config.embedding_dimension:
        mismatches.append("embedding dimension")
    if manifest.normalization_method != config.normalization_method:
        mismatches.append("normalization method")
    if manifest.chunking_configuration_fingerprint != chunking_configuration_fingerprint:
        mismatches.append("chunking configuration fingerprint")
    if mismatches:
        raise ManifestCompatibilityError(
            "Incompatible retrieval index manifest: " + ", ".join(mismatches)
        )
