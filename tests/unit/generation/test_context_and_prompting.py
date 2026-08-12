"""Tests for bounded context selection and provider-neutral prompting."""

from financial_rag.generation.context import ContextAssembler, ContextAssemblyConfig
from financial_rag.generation.prompting import build_grounded_prompt
from tests.unit.generation.helpers import retrieval_result


def test_context_assembly_uses_at_most_top_five_in_retrieval_order() -> None:
    assembled = ContextAssembler().assemble(retrieval_result(6))

    assert [item.citation_id for item in assembled.items] == ["C1", "C2", "C3", "C4", "C5"]
    assert [item.chunk.rank for item in assembled.items] == [1, 2, 3, 4, 5]


def test_context_budget_truncates_deterministically() -> None:
    assembled = ContextAssembler(ContextAssemblyConfig(top_k=5, token_budget=3)).assemble(
        retrieval_result(2)
    )

    assert len(assembled.items) == 1
    assert assembled.items[0].content == "financial evidence number"
    assert assembled.items[0].content_truncated is True
    assert assembled.estimated_token_count == 3


def test_prompt_contains_only_stable_labels_and_lineage() -> None:
    assembled = ContextAssembler(ContextAssemblyConfig(top_k=1)).assemble(retrieval_result(1))

    prompt = build_grounded_prompt("What changed?", assembled)

    assert "[C1]" in prompt.input_text
    assert "chunk_id:" in prompt.input_text
    assert "source_file:" in prompt.input_text
    assert "only from the supplied" in prompt.instructions
