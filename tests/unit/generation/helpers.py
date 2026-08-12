"""Synthetic retrieval and generation helpers with no external calls."""

from financial_rag.domain.generation import GenerationPrompt, GenerationResult, ModelAnswer
from financial_rag.domain.metadata import ChunkMetadata
from financial_rag.domain.retrieval import RetrievalMode, RetrievalResult, RetrievedChunk
from financial_rag.generation.protocols import GenerationAdapter
from tests.unit.retrieval.helpers import fake_retrieval_config, synthetic_chunks


def retrieval_result(count: int = 6) -> RetrievalResult:
    """Build ranked synthetic chunks without an index or model."""
    documents = synthetic_chunks([f"financial evidence number {index}" for index in range(count)])
    chunks: list[RetrievedChunk] = []
    for rank, document in enumerate(documents, start=1):
        metadata = ChunkMetadata.model_validate(document.metadata)
        chunks.append(
            RetrievedChunk(
                **metadata.model_dump(),
                content=document.page_content,
                rank=rank,
                dense_rank=rank,
                dense_score=1.0 / rank,
            )
        )
    config = fake_retrieval_config(final_top_k=max(1, count))
    return RetrievalResult(
        query="What is the financial evidence?",
        expanded_query="What is the financial evidence?",
        mode=RetrievalMode.DENSE,
        retrieval_configuration_fingerprint=config.fingerprint,
        chunks=tuple(chunks),
    )


class FakeGenerationAdapter(GenerationAdapter):
    """Return a predetermined structured answer and retain the prompt for assertions."""

    def __init__(self, answer: ModelAnswer) -> None:
        self._answer = answer
        self.prompt: GenerationPrompt | None = None

    @property
    def model_identifier(self) -> str:
        return "fake-generator-v1"

    def generate(self, prompt: GenerationPrompt) -> GenerationResult:
        self.prompt = prompt
        return GenerationResult(answer=self._answer, model_identifier=self.model_identifier)
