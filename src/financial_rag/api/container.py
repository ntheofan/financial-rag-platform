"""Explicit dependency container for side-effect-free application construction."""

from dataclasses import dataclass

from financial_rag.api.protocols import (
    CorpusIndexingUseCase,
    EvaluationUseCase,
    GroundedGenerationUseCase,
    RetrievalUseCase,
    RevisionReader,
)


@dataclass(slots=True)
class ApiContainer:
    """Services available to one FastAPI application instance."""

    retrieval: RetrievalUseCase | None = None
    generation: GroundedGenerationUseCase | None = None
    evaluation: EvaluationUseCase | None = None
    revisions: RevisionReader | None = None
    indexing: CorpusIndexingUseCase | None = None

    def replace_query_services(
        self,
        *,
        retrieval: RetrievalUseCase,
        generation: GroundedGenerationUseCase | None,
        evaluation: EvaluationUseCase,
    ) -> None:
        """Replace the local single-user query bundle after index activation."""
        self.retrieval = retrieval
        self.generation = generation
        self.evaluation = evaluation
