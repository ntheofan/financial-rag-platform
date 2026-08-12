"""Grounding and abstention tests around fake retrieval and generation ports."""

import pytest

from financial_rag.core.errors import CitationValidationError
from financial_rag.domain.generation import ModelAnswer
from financial_rag.domain.retrieval import RetrievalMode, RetrievalResult
from financial_rag.generation.service import GroundedGenerationService
from tests.unit.generation.helpers import FakeGenerationAdapter, retrieval_result


class StubRetrieval:
    """Return one predetermined retrieval result."""

    def __init__(self, result: RetrievalResult) -> None:
        self._result = result

    def retrieve(self, query: str, *, mode: RetrievalMode) -> RetrievalResult:
        del query, mode
        return self._result


def _service(answer: ModelAnswer) -> tuple[GroundedGenerationService, FakeGenerationAdapter]:
    adapter = FakeGenerationAdapter(answer)
    return (
        GroundedGenerationService(
            retrieval=StubRetrieval(retrieval_result()),
            generator=adapter,
        ),
        adapter,
    )


def test_grounded_answer_maps_citation_to_full_chunk_lineage() -> None:
    service, adapter = _service(
        ModelAnswer(answer="Capital expenditure increased.", abstained=False, citation_ids=("C1",))
    )

    answer = service.answer("What changed?", mode=RetrievalMode.DENSE)

    assert answer.citations[0].chunk_id == answer.contexts[0].chunk.chunk_id
    assert answer.citations[0].source_file == answer.contexts[0].chunk.source_file
    assert answer.retrieval.chunks[0].dense_score is not None
    assert adapter.prompt is not None


@pytest.mark.parametrize(
    "answer",
    [
        ModelAnswer(answer="Unsupported.", abstained=False),
        ModelAnswer(answer="Unsupported.", abstained=False, citation_ids=("C6",)),
        ModelAnswer(answer="No answer.", abstained=True, citation_ids=("C1",)),
        ModelAnswer(answer="Duplicate.", abstained=False, citation_ids=("C1", "C1")),
    ],
)
def test_invalid_grounding_is_rejected(answer: ModelAnswer) -> None:
    service, _ = _service(answer)

    with pytest.raises(CitationValidationError):
        service.answer("What changed?", mode=RetrievalMode.HYBRID)


def test_valid_abstention_has_no_citations() -> None:
    service, _ = _service(ModelAnswer(answer="The context is insufficient.", abstained=True))

    answer = service.answer("What changed?", mode=RetrievalMode.HYBRID)

    assert answer.abstained is True
    assert answer.citations == ()


def test_empty_retrieval_abstains_without_calling_provider() -> None:
    adapter = FakeGenerationAdapter(
        ModelAnswer(answer="Should not be used.", abstained=False, citation_ids=("C1",))
    )
    service = GroundedGenerationService(
        retrieval=StubRetrieval(retrieval_result(0)),
        generator=adapter,
    )

    answer = service.answer("What changed?", mode=RetrievalMode.DENSE)

    assert answer.abstained is True
    assert answer.model_identifier == "local:no-context-policy"
    assert adapter.prompt is None
