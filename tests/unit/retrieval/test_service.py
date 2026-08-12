"""End-to-end offline tests for V1, V2, and V3 retrieval routing."""

import pytest

from financial_rag.core.errors import (
    EmptyCorpusError,
    EmptyQueryError,
    InvalidEmbeddingError,
    RerankerRequiredError,
    RetrievalError,
)
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.fingerprints import fingerprint_model
from financial_rag.domain.retrieval import RetrievalMode
from financial_rag.retrieval.embeddings import FakeEmbeddingProvider
from financial_rag.retrieval.rerankers import FakeReranker
from financial_rag.retrieval.service import RetrievalService
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks

CORPUS_TEXTS = [
    "capital expenditures purchases property plant equipment cash flow statement",
    "revenue net sales income statement",
    "working capital current assets current liabilities balance sheet",
    "unrelated risk factors and litigation",
]


def _service(*, reranker: FakeReranker | None = None) -> RetrievalService:
    config = fake_retrieval_config(final_top_k=3)
    return RetrievalService.build(
        synthetic_chunks(CORPUS_TEXTS),
        embedding_provider=FakeEmbeddingProvider(dimension=config.embedding_dimension),
        config=config,
        chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        reranker=reranker,
    )


@pytest.mark.parametrize(
    "mode",
    [RetrievalMode.DENSE, RetrievalMode.HYBRID, RetrievalMode.HYBRID_RERANKED],
)
def test_v1_v2_v3_route_through_one_result_contract(mode: RetrievalMode) -> None:
    """All modes return contiguous ranks and the same metadata-rich schema."""
    service = _service(reranker=FakeReranker())

    result = service.retrieve("capex", mode=mode)

    assert result.mode is mode
    assert result.document_unknown is True
    assert [chunk.rank for chunk in result.chunks] == list(range(1, len(result.chunks) + 1))
    assert all(chunk.source_file == "synthetic/acme-2025-10k.md" for chunk in result.chunks)
    assert all(chunk.company == "ACME Corp" for chunk in result.chunks)
    assert all(chunk.page_number is not None for chunk in result.chunks)
    assert all(chunk.section_heading is not None for chunk in result.chunks)
    if mode is RetrievalMode.DENSE:
        assert all(chunk.dense_score is not None for chunk in result.chunks)
        assert all(chunk.rrf_score is None for chunk in result.chunks)
    elif mode is RetrievalMode.HYBRID:
        assert all(chunk.rrf_score is not None for chunk in result.chunks)
        assert all(chunk.rerank_score is None for chunk in result.chunks)
    else:
        assert all(chunk.rerank_score is not None for chunk in result.chunks)


def test_fake_reranker_changes_the_intended_hybrid_ranking() -> None:
    """V3 scores the full hybrid pool before selecting final top-k."""
    boosted_text = CORPUS_TEXTS[-1]
    service = _service(reranker=FakeReranker({boosted_text: 100.0}))

    hybrid = service.retrieve("capex", mode=RetrievalMode.HYBRID)
    reranked = service.retrieve("capex", mode=RetrievalMode.HYBRID_RERANKED)

    assert hybrid.chunks[0].content != boosted_text
    assert reranked.chunks[0].content == boosted_text
    assert reranked.chunks[0].rerank_score == 100.0


def test_v3_requires_an_explicit_reranker() -> None:
    """The service cannot silently degrade V3 into V2."""
    with pytest.raises(RerankerRequiredError):
        _service().retrieve("capex", mode=RetrievalMode.HYBRID_RERANKED)


def test_retrieval_rejects_blank_queries() -> None:
    """Empty query handling is consistent before embedding or index search."""
    with pytest.raises(EmptyQueryError):
        _service().retrieve("  ", mode=RetrievalMode.DENSE)


def test_build_rejects_empty_corpus() -> None:
    """Index construction requires at least one validated ingestion chunk."""
    config = fake_retrieval_config()
    with pytest.raises(EmptyCorpusError):
        RetrievalService.build(
            [],
            embedding_provider=FakeEmbeddingProvider(dimension=config.embedding_dimension),
            config=config,
            chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        )


def test_build_rejects_provider_configuration_mismatch() -> None:
    """Model identifiers and dimensions cannot drift from the versioned config."""
    config = fake_retrieval_config()
    with pytest.raises(InvalidEmbeddingError, match="model identifier"):
        RetrievalService.build(
            synthetic_chunks(["synthetic"]),
            embedding_provider=FakeEmbeddingProvider(
                dimension=config.embedding_dimension,
                model_identifier="different-fake",
            ),
            config=config,
            chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
        )


def test_build_rejects_reranker_configuration_mismatch() -> None:
    """V3 cannot silently execute a reranker different from the versioned config."""
    config = fake_retrieval_config().model_copy(
        update={"reranker_model_identifier": "expected-reranker"}
    )
    with pytest.raises(RetrievalError, match="Reranker is incompatible"):
        RetrievalService.build(
            synthetic_chunks(["synthetic"]),
            embedding_provider=FakeEmbeddingProvider(dimension=config.embedding_dimension),
            config=config,
            chunking_configuration_fingerprint=fingerprint_model(ChunkingConfig()),
            reranker=FakeReranker(),
        )
