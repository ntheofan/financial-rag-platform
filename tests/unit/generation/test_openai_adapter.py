"""Official SDK adapter tests using an in-memory fake client only."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from financial_rag.core.errors import GenerationProviderError
from financial_rag.domain.generation import GenerationPrompt, ModelAnswer
from financial_rag.generation.openai_adapter import (
    OpenAIGenerationConfig,
    OpenAIResponsesAdapter,
)


class FakeResponses:
    """Capture structured Responses API arguments without network access."""

    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.kwargs: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> object:
        self.kwargs = kwargs
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _prompt() -> GenerationPrompt:
    return GenerationPrompt(instructions="Ground answers.", input_text="Question and C1")


def test_adapter_requests_pydantic_structured_output_and_maps_usage() -> None:
    responses = FakeResponses(
        SimpleNamespace(
            output_parsed=ModelAnswer(answer="Answer.", abstained=False, citation_ids=("C1",)),
            usage=SimpleNamespace(input_tokens=10, output_tokens=4, total_tokens=14),
        )
    )
    client = SimpleNamespace(responses=responses)
    adapter = OpenAIResponsesAdapter(
        api_key=SecretStr("test-only"),
        config=OpenAIGenerationConfig(model_identifier="test-model", max_output_tokens=100),
        client=client,
    )

    result = adapter.generate(_prompt())

    assert responses.kwargs["text_format"] is ModelAnswer
    assert responses.kwargs["store"] is False
    assert responses.kwargs["max_output_tokens"] == 100
    assert result.usage.total_tokens == 14
    assert result.model_identifier == "test-model"


def test_adapter_converts_provider_failure_to_safe_domain_error() -> None:
    client = SimpleNamespace(responses=FakeResponses(error=RuntimeError("sensitive")))
    adapter = OpenAIResponsesAdapter(api_key=SecretStr("test-only"), client=client)

    with pytest.raises(GenerationProviderError, match="request failed"):
        adapter.generate(_prompt())


def test_adapter_builds_official_client_lazily_with_secret_safe_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeOpenAIError(Exception):
        pass

    def client_factory(**kwargs: Any) -> object:
        captured.update(kwargs)
        return SimpleNamespace(responses=FakeResponses())

    fake_module = SimpleNamespace(OpenAI=client_factory, OpenAIError=FakeOpenAIError)
    monkeypatch.setattr(
        "financial_rag.generation.openai_adapter.importlib.import_module",
        lambda _name: fake_module,
    )

    OpenAIResponsesAdapter(
        api_key=SecretStr("secret-value"),
        config=OpenAIGenerationConfig(timeout_seconds=12, max_retries=1),
    )

    assert captured == {"api_key": "secret-value", "timeout": 12.0, "max_retries": 1}


def test_adapter_rejects_missing_or_malformed_structured_output() -> None:
    response = SimpleNamespace(output_parsed=None, output_text="not-json", usage=None)
    adapter = OpenAIResponsesAdapter(
        api_key=SecretStr("test-only"),
        client=SimpleNamespace(responses=FakeResponses(response)),
    )

    with pytest.raises(GenerationProviderError, match="no valid structured answer"):
        adapter.generate(_prompt())
