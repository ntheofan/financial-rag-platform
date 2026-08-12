"""FastAPI dependency accessors for explicitly injected services."""

from typing import Annotated, cast

from fastapi import Depends, Request

from financial_rag.api.container import ApiContainer
from financial_rag.api.errors import ApiServiceUnavailableError
from financial_rag.api.protocols import (
    CorpusIndexingUseCase,
    EvaluationUseCase,
    GroundedGenerationUseCase,
    RetrievalUseCase,
    RevisionReader,
)


def get_container(request: Request) -> ApiContainer:
    """Read the immutable container installed by the application factory."""
    return cast(ApiContainer, request.app.state.container)


ContainerDependency = Annotated[ApiContainer, Depends(get_container)]


def require_retrieval(container: ContainerDependency) -> RetrievalUseCase:
    """Fail clearly when no local retrieval runtime was injected."""
    if container.retrieval is None:
        raise ApiServiceUnavailableError
    return container.retrieval


def require_revisions(container: ContainerDependency) -> RevisionReader:
    """Fail clearly when no revision reader was injected."""
    if container.revisions is None:
        raise ApiServiceUnavailableError
    return container.revisions


def require_generation(container: ContainerDependency) -> GroundedGenerationUseCase:
    """Fail clearly when grounded generation was not configured."""
    if container.generation is None:
        raise ApiServiceUnavailableError
    return container.generation


def require_evaluation(container: ContainerDependency) -> EvaluationUseCase:
    """Fail clearly when paired evaluation was not configured."""
    if container.evaluation is None:
        raise ApiServiceUnavailableError
    return container.evaluation


def require_indexing(container: ContainerDependency) -> CorpusIndexingUseCase:
    """Fail clearly when local corpus management was not configured."""
    if container.indexing is None:
        raise ApiServiceUnavailableError
    return container.indexing


RetrievalDependency = Annotated[RetrievalUseCase, Depends(require_retrieval)]
GenerationDependency = Annotated[GroundedGenerationUseCase, Depends(require_generation)]
EvaluationDependency = Annotated[EvaluationUseCase, Depends(require_evaluation)]
RevisionDependency = Annotated[RevisionReader, Depends(require_revisions)]
IndexingDependency = Annotated[CorpusIndexingUseCase, Depends(require_indexing)]
