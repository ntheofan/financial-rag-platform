"""Grounded retrieval-to-answer orchestration with strict citation validation."""

import structlog

from financial_rag.api.protocols import RetrievalUseCase
from financial_rag.core.errors import CitationValidationError
from financial_rag.domain.generation import (
    AnswerCitation,
    CitationContext,
    GenerationResult,
    GroundedAnswer,
    ModelAnswer,
)
from financial_rag.domain.retrieval import RetrievalMode
from financial_rag.generation.context import ContextAssembler
from financial_rag.generation.prompting import build_grounded_prompt
from financial_rag.generation.protocols import GenerationAdapter

logger = structlog.get_logger(__name__)
NO_CONTEXT_ANSWER = "I cannot answer from the retrieved document context."


class GroundedGenerationService:
    """Retrieve, assemble, generate, and validate one grounded answer."""

    def __init__(
        self,
        *,
        retrieval: RetrievalUseCase,
        generator: GenerationAdapter,
        context_assembler: ContextAssembler | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._generator = generator
        self._context_assembler = context_assembler or ContextAssembler()

    def answer(self, query: str, *, mode: RetrievalMode) -> GroundedAnswer:
        """Return an answer whose citations are restricted to the supplied top-five context."""
        retrieval = self._retrieval.retrieve(query, mode=mode)
        contexts = self._context_assembler.assemble(retrieval)
        if not contexts.items:
            generated = GenerationResult(
                answer=ModelAnswer(answer=NO_CONTEXT_ANSWER, abstained=True),
                model_identifier="local:no-context-policy",
            )
        else:
            prompt = build_grounded_prompt(query, contexts)
            generated = self._generator.generate(prompt)
        citations = self._validate_and_map(generated.answer, contexts.items)
        logger.info(
            "grounded_answer_completed",
            mode=mode.value,
            abstained=generated.answer.abstained,
            citation_count=len(citations),
            context_count=len(contexts.items),
            model=generated.model_identifier,
        )
        return GroundedAnswer(
            answer=generated.answer.answer,
            abstained=generated.answer.abstained,
            citations=citations,
            contexts=contexts.items,
            retrieval=retrieval,
            model_identifier=generated.model_identifier,
            usage=generated.usage,
        )

    @staticmethod
    def _validate_and_map(
        answer: ModelAnswer,
        contexts: tuple[CitationContext, ...],
    ) -> tuple[AnswerCitation, ...]:
        if len(answer.citation_ids) != len(set(answer.citation_ids)):
            raise CitationValidationError("Generated citation IDs must be unique.")
        if answer.abstained and answer.citation_ids:
            raise CitationValidationError("An abstained answer cannot contain citations.")
        if not answer.abstained and not answer.citation_ids:
            raise CitationValidationError("A generated answer must cite supplied context.")
        by_id = {item.citation_id: item for item in contexts}
        unknown = [citation_id for citation_id in answer.citation_ids if citation_id not in by_id]
        if unknown:
            raise CitationValidationError("Generated answer referenced an unknown citation ID.")
        return tuple(
            AnswerCitation(
                citation_id=citation_id,
                chunk_id=by_id[citation_id].chunk.chunk_id,
                document_id=by_id[citation_id].chunk.document_id,
                source_file=by_id[citation_id].chunk.source_file,
                page_number=by_id[citation_id].chunk.page_number,
                section_heading=by_id[citation_id].chunk.section_heading,
                retrieval_rank=by_id[citation_id].chunk.rank,
            )
            for citation_id in answer.citation_ids
        )
