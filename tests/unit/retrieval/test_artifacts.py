"""Tests for ignored local FAISS, mapping, and manifest save/load."""

import json
import shutil
from pathlib import Path

import pytest

from financial_rag.core.errors import (
    ManifestCompatibilityError,
    RetrievalArtifactError,
)
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.fingerprints import fingerprint_model
from financial_rag.domain.retrieval import RetrievalMode
from financial_rag.retrieval.artifacts import (
    INDEX_FILENAME,
    MANIFEST_FILENAME,
    MAPPING_FILENAME,
    DenseIndexArtifactStore,
)
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from financial_rag.retrieval.service import RetrievalService
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks


def _built_service() -> tuple[RetrievalService, FakeEmbeddingProvider]:
    config = fake_retrieval_config()
    provider = FakeEmbeddingProvider(dimension=config.embedding_dimension)
    service = RetrievalService.build(
        synthetic_chunks(["revenue growth", "cash flow", "risk factors"]),
        embedding_provider=provider,
        config=config,
        chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
    )
    return service, provider


def test_faiss_artifact_round_trip_preserves_ranking(tmp_path: Path) -> None:
    """Index, mapping, and manifest restore the same deterministic result IDs."""
    service, provider = _built_service()
    artifact_directory = tmp_path / "retrieval-artifacts"
    service.save_artifacts(artifact_directory)

    assert (artifact_directory / INDEX_FILENAME).is_file()
    assert (artifact_directory / MAPPING_FILENAME).is_file()
    assert (artifact_directory / MANIFEST_FILENAME).is_file()

    restored = RetrievalService.load_artifacts(
        artifact_directory,
        embedding_provider=provider,
        config=fake_retrieval_config(),
        chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
    )
    before = service.retrieve("revenue growth", mode=RetrievalMode.DENSE)
    after = restored.retrieve("revenue growth", mode=RetrievalMode.DENSE)

    assert [chunk.chunk_id for chunk in before.chunks] == [chunk.chunk_id for chunk in after.chunks]


def test_load_rejects_incompatible_manifest(tmp_path: Path) -> None:
    """A different embedding model cannot search a persisted index."""
    service, _provider = _built_service()
    artifact_directory = tmp_path / "retrieval-artifacts"
    service.save_artifacts(artifact_directory)
    incompatible = fake_retrieval_config().model_copy(
        update={"embedding_model_identifier": "other/model"}
    )

    with pytest.raises(ManifestCompatibilityError, match="embedding model"):
        DenseIndexArtifactStore().load(
            artifact_directory,
            config=incompatible,
            chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        )


def test_load_rejects_reordered_chunk_mapping(tmp_path: Path) -> None:
    """The ordered mapping fingerprint detects metadata-row misalignment."""
    service, _provider = _built_service()
    artifact_directory = tmp_path / "retrieval-artifacts"
    service.save_artifacts(artifact_directory)
    mapping_path = artifact_directory / MAPPING_FILENAME
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    payload["chunks"].reverse()
    mapping_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RetrievalArtifactError, match="mapping fingerprint"):
        DenseIndexArtifactStore().load(
            artifact_directory,
            config=fake_retrieval_config(),
            chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        )


def test_load_rejects_faiss_index_from_another_artifact_set(tmp_path: Path) -> None:
    """Vector fingerprints detect an interrupted or mixed multi-file save."""
    service, _provider = _built_service()
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    service.save_artifacts(first_directory)

    config = fake_retrieval_config()
    other_service = RetrievalService.build(
        synthetic_chunks(["different alpha", "different beta", "different gamma"]),
        embedding_provider=FakeEmbeddingProvider(dimension=config.embedding_dimension),
        config=config,
        chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
    )
    other_service.save_artifacts(second_directory)
    shutil.copyfile(second_directory / INDEX_FILENAME, first_directory / INDEX_FILENAME)

    with pytest.raises(RetrievalArtifactError, match="vector fingerprint"):
        DenseIndexArtifactStore().load(
            first_directory,
            config=config,
            chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        )


def test_load_rejects_incomplete_artifact_set(tmp_path: Path) -> None:
    """Missing local files produce one clear domain error."""
    with pytest.raises(RetrievalArtifactError, match="incomplete"):
        DenseIndexArtifactStore().load(
            tmp_path,
            config=fake_retrieval_config(),
            chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        )
