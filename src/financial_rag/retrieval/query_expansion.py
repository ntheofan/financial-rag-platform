"""Versioned deterministic finance query expansion."""

import re

from financial_rag.core.errors import EmptyQueryError
from financial_rag.domain.retrieval import QueryExpansionConfig


def normalize_query_text(query: str) -> str:
    """Lowercase and collapse query whitespace without semantic rewriting."""
    normalized = re.sub(r"\s+", " ", query).strip().casefold()
    if not normalized:
        raise EmptyQueryError("Query cannot be blank")
    return normalized


class FinanceQueryExpander:
    """Apply immutable alias rules in longest-alias-first order."""

    def __init__(self, config: QueryExpansionConfig) -> None:
        self.config = config

    def expand(self, query: str) -> str:
        """Return a normalized query with stable, de-duplicated expansions."""
        normalized = normalize_query_text(query)
        if not self.config.enabled:
            return normalized

        ordered_rules = sorted(
            self.config.rules,
            key=lambda rule: (-len(rule.alias), rule.alias.casefold()),
        )
        seen: set[str] = set()
        expansions: list[str] = []
        for rule in ordered_rules:
            if rule.alias.casefold() not in normalized:
                continue
            for expansion in rule.expansions:
                cleaned = normalize_query_text(expansion)
                if cleaned not in seen:
                    seen.add(cleaned)
                    expansions.append(cleaned)
        return " ".join([normalized, *expansions])
