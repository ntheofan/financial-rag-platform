"""Lazy official OpenAI Responses API adapter with structured output parsing."""

import importlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from financial_rag.core.errors import GenerationProviderError, ProviderUnavailableError
from financial_rag.domain.generation import (
    GenerationPrompt,
    GenerationResult,
    GenerationUsage,
    ModelAnswer,
)


class OpenAIGenerationConfig(BaseModel):
    """Explicit request bounds for one OpenAI generation adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_identifier: str = Field(default="gpt-4o-mini", min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_output_tokens: int = Field(default=1000, gt=0)


class OpenAIResponsesAdapter:
    """Call structured Responses API output without import-time SDK or network access."""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        config: OpenAIGenerationConfig | None = None,
        client: Any | None = None,
    ) -> None:
        self._config = config or OpenAIGenerationConfig()
        if client is not None:
            self._client = client
            self._provider_errors: tuple[type[BaseException], ...] = (Exception,)
            return
        try:
            module = importlib.import_module("openai")
            self._client = module.OpenAI(
                api_key=api_key.get_secret_value(),
                timeout=self._config.timeout_seconds,
                max_retries=self._config.max_retries,
            )
            self._provider_errors = (module.OpenAIError,)
        except (ImportError, AttributeError) as exc:
            raise ProviderUnavailableError(
                "The official OpenAI Python SDK is unavailable. Install runtime dependencies."
            ) from exc

    @property
    def model_identifier(self) -> str:
        return self._config.model_identifier

    def generate(self, prompt: GenerationPrompt) -> GenerationResult:
        """Request Pydantic-structured output and convert provider failures safely."""
        try:
            response = self._client.responses.parse(
                model=self.model_identifier,
                instructions=prompt.instructions,
                input=prompt.input_text,
                text_format=ModelAnswer,
                max_output_tokens=self._config.max_output_tokens,
                store=False,
            )
        except self._provider_errors as exc:
            raise GenerationProviderError("The generation provider request failed.") from exc
        except ValueError as exc:
            raise GenerationProviderError(
                "The generation provider returned invalid structured output."
            ) from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            try:
                parsed = ModelAnswer.model_validate_json(response.output_text)
            except (AttributeError, ValueError) as exc:
                raise GenerationProviderError(
                    "The generation provider returned no valid structured answer."
                ) from exc
        try:
            answer = (
                parsed if isinstance(parsed, ModelAnswer) else ModelAnswer.model_validate(parsed)
            )
        except ValueError as exc:
            raise GenerationProviderError(
                "The generation provider returned an invalid structured answer."
            ) from exc

        raw_usage = getattr(response, "usage", None)
        usage = GenerationUsage(
            input_tokens=getattr(raw_usage, "input_tokens", None),
            output_tokens=getattr(raw_usage, "output_tokens", None),
            total_tokens=getattr(raw_usage, "total_tokens", None),
        )
        return GenerationResult(
            answer=answer,
            model_identifier=self.model_identifier,
            usage=usage,
        )
