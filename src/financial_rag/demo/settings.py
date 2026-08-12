"""Non-secret settings for the local Streamlit HTTP client."""

from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DemoSettings(BaseSettings):
    """Configure only the FastAPI boundary; never accept provider credentials."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    financial_rag_api_url: str = "http://127.0.0.1:8000"
    demo_request_timeout_seconds: float = Field(default=90.0, gt=0, le=300)

    @field_validator("financial_rag_api_url")
    @classmethod
    def api_url_must_be_http(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("FINANCIAL_RAG_API_URL must be an absolute HTTP(S) URL")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("FINANCIAL_RAG_API_URL cannot contain credentials, query, or fragment")
        return normalized
