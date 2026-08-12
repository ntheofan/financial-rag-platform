"""Pure display-helper and non-secret settings tests."""

import pytest
from pydantic import ValidationError

from financial_rag.demo.presentation import available_scores, source_label, top_chunk_overlap
from financial_rag.demo.settings import DemoSettings
from tests.unit.generation.helpers import retrieval_result


def test_source_label_and_scores_preserve_available_lineage() -> None:
    chunk = retrieval_result(1).chunks[0]

    assert "synthetic/acme-2025-10k.md" in source_label(chunk)
    assert "page 1" in source_label(chunk)
    assert [(score.label, score.value) for score in available_scores(chunk)] == [("Dense", 1.0)]


def test_overlap_uses_chunk_identity_not_rank_or_text() -> None:
    chunks = retrieval_result(3).chunks

    assert top_chunk_overlap(chunks[:2], chunks[1:]) == pytest.approx(1 / 3)
    assert top_chunk_overlap((), ()) == 1.0


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "ftp://localhost:8000",
        "http://user:password@localhost:8000",
        "http://localhost:8000?secret=value",
    ],
)
def test_demo_api_url_rejects_unsafe_or_invalid_values(url: str) -> None:
    with pytest.raises(ValidationError):
        DemoSettings(financial_rag_api_url=url)


def test_demo_settings_normalize_trailing_slash() -> None:
    settings = DemoSettings(financial_rag_api_url="http://127.0.0.1:8000/")

    assert settings.financial_rag_api_url == "http://127.0.0.1:8000"


def test_demo_settings_have_no_provider_secret_field() -> None:
    assert all("openai" not in name for name in DemoSettings.model_fields)
    assert all("api_key" not in name for name in DemoSettings.model_fields)
