"""Tests for deterministic versioned finance query expansion."""

from financial_rag.domain.retrieval import QueryExpansionConfig, RetrievalConfig
from financial_rag.retrieval.query_expansion import FinanceQueryExpander
from tests.unit.retrieval.helpers import PLATFORM_CONFIG_PATH


def test_finance_alias_expansion_is_deterministic() -> None:
    """The migrated CAPEX alias expands in a stable, de-duplicated order."""
    config = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)
    expander = FinanceQueryExpander(config.query_expansion)

    first = expander.expand("  What was CAPEX at year-end?  ")
    second = expander.expand("  What was CAPEX at year-end?  ")

    assert first == second
    assert first.startswith("what was capex at year-end?")
    assert "capital expenditure" in first
    assert "at december 31" in first
    assert first.count("balance sheet") == 1


def test_query_expansion_can_be_disabled_explicitly() -> None:
    """Controlled comparisons may normalize without appending aliases."""
    expander = FinanceQueryExpander(QueryExpansionConfig(enabled=False))
    assert expander.expand("  Cash   Flow ") == "cash flow"
