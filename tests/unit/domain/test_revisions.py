"""Deterministic revision identity and validation tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from financial_rag.domain.fingerprints import fingerprint_payload
from financial_rag.domain.revisions import CorpusRevision, make_corpus_revision_id
from financial_rag.retrieval.corpus import records_from_documents
from tests.unit.retrieval.helpers import synthetic_chunks


def test_corpus_revision_id_is_deterministic_and_order_sensitive() -> None:
    records = records_from_documents(synthetic_chunks(["revenue increased", "cash decreased"]))
    chunking = fingerprint_payload({"chunk_size": 1500, "chunk_overlap": 200})

    first = make_corpus_revision_id(records, chunking_configuration_fingerprint=chunking)
    repeated = make_corpus_revision_id(records, chunking_configuration_fingerprint=chunking)
    reversed_id = make_corpus_revision_id(
        tuple(reversed(records)), chunking_configuration_fingerprint=chunking
    )

    assert first == repeated
    assert first != reversed_id


def test_corpus_revision_id_changes_with_chunking_configuration() -> None:
    records = records_from_documents(synthetic_chunks(["synthetic filing content"]))

    first = make_corpus_revision_id(
        records,
        chunking_configuration_fingerprint=fingerprint_payload({"chunk_size": 1500}),
    )
    second = make_corpus_revision_id(
        records,
        chunking_configuration_fingerprint=fingerprint_payload({"chunk_size": 1200}),
    )

    assert first != second


def test_revision_requires_timezone_aware_timestamp() -> None:
    fingerprint = fingerprint_payload({"value": "synthetic"})

    with pytest.raises(ValidationError, match="timezone-aware"):
        CorpusRevision(
            corpus_revision_id="corpus_" + "a" * 32,
            status="ready",
            chunking_configuration_fingerprint=fingerprint,
            chunk_mapping_fingerprint=fingerprint,
            document_count=1,
            chunk_count=1,
            created_at=datetime(2026, 8, 1),
        )

    revision = CorpusRevision(
        corpus_revision_id="corpus_" + "a" * 32,
        status="ready",
        chunking_configuration_fingerprint=fingerprint,
        chunk_mapping_fingerprint=fingerprint,
        document_count=1,
        chunk_count=1,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert revision.status == "ready"
