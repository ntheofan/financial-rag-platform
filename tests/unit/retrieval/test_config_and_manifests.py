"""Tests for platform_v1 configuration and artifact compatibility."""

from datetime import UTC, datetime

import pytest

from financial_rag.core.errors import ManifestCompatibilityError
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.fingerprints import fingerprint_model
from financial_rag.domain.retrieval import RetrievalConfig
from financial_rag.retrieval.corpus import records_from_documents
from financial_rag.retrieval.manifests import (
    create_index_manifest,
    validate_manifest_compatibility,
)
from tests.unit.retrieval.helpers import PLATFORM_CONFIG_PATH, synthetic_chunks


def test_versioned_config_preserves_thesis_protocol_defaults() -> None:
    """The checked-in platform_v1 config keeps all approved retrieval defaults."""
    config = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)

    assert config.embedding_model_identifier == "BAAI/bge-m3"
    assert config.embedding_dimension == 1024
    assert config.normalization_method == "l2"
    assert config.dense_index_type == "faiss_index_flat_ip"
    assert (config.bm25_k1, config.bm25_b) == (1.5, 0.75)
    assert (config.dense_candidate_count, config.bm25_candidate_count) == (20, 10)
    assert (config.rrf_k, config.dense_rrf_weight, config.bm25_rrf_weight) == (
        30,
        1.0,
        0.2,
    )
    assert config.final_top_k == 10
    assert config.reranker_model_identifier == "BAAI/bge-reranker-v2-m3"
    assert config.query_expansion.version == "finance_aliases_v1"


def test_configuration_fingerprint_is_deterministic_and_sensitive() -> None:
    """Equivalent configs hash identically while one changed parameter does not."""
    first = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)
    second = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)
    changed = first.model_copy(update={"rrf_k": 31})

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != changed.fingerprint


def test_manifest_contains_required_compatibility_lineage() -> None:
    """Manifest records model, dimensions, configs, ordered mapping, count, and time."""
    config = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)
    records = records_from_documents(synthetic_chunks(["alpha", "beta"]))
    chunking_fingerprint = fingerprint_model(ChunkingConfig())
    timestamp = datetime(2026, 8, 1, 12, tzinfo=UTC)

    manifest = create_index_manifest(
        config=config,
        chunking_configuration_fingerprint=chunking_fingerprint,
        records=records,
        index_vector_fingerprint=fingerprint_model(ChunkingConfig()),
        creation_timestamp=timestamp,
    )

    assert manifest.platform_version == "platform_v1"
    assert manifest.corpus_chunk_count == 2
    assert manifest.creation_timestamp == timestamp
    assert manifest.retrieval_configuration_fingerprint == config.fingerprint
    assert manifest.chunk_mapping_fingerprint.value


@pytest.mark.parametrize(
    ("config_update", "manifest_update", "expected"),
    [
        ({"embedding_model_identifier": "other/model"}, {}, "embedding model"),
        ({"embedding_dimension": 64}, {}, "embedding dimension"),
        ({}, {"normalization_method": "none"}, "normalization method"),
    ],
)
def test_manifest_rejects_incompatible_embedding_semantics(
    config_update: dict[str, object],
    manifest_update: dict[str, object],
    expected: str,
) -> None:
    """Search/load is blocked for model, dimension, or normalization mismatches."""
    config = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)
    chunking_fingerprint = fingerprint_model(ChunkingConfig())
    records = records_from_documents(synthetic_chunks(["alpha"]))
    manifest = create_index_manifest(
        config=config,
        chunking_configuration_fingerprint=chunking_fingerprint,
        records=records,
        index_vector_fingerprint=fingerprint_model(ChunkingConfig()),
    ).model_copy(update=manifest_update)
    expected_config = config.model_copy(update=config_update)

    with pytest.raises(ManifestCompatibilityError, match=expected):
        validate_manifest_compatibility(
            manifest,
            config=expected_config,
            chunking_configuration_fingerprint=chunking_fingerprint,
        )


def test_manifest_rejects_incompatible_chunking_fingerprint() -> None:
    """A changed chunking protocol requires a new incompatible index."""
    config = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)
    original = fingerprint_model(ChunkingConfig())
    changed = fingerprint_model(ChunkingConfig(chunk_size=1400))
    records = records_from_documents(synthetic_chunks(["alpha"]))
    manifest = create_index_manifest(
        config=config,
        chunking_configuration_fingerprint=original,
        records=records,
        index_vector_fingerprint=fingerprint_model(ChunkingConfig()),
    )

    with pytest.raises(ManifestCompatibilityError, match="chunking configuration"):
        validate_manifest_compatibility(
            manifest,
            config=config,
            chunking_configuration_fingerprint=changed,
        )
