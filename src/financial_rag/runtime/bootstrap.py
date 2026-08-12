"""Explicit composition root for the local, single-user application runtime."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import structlog
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from financial_rag.api.container import ApiContainer
from financial_rag.chunking.service import MarkdownChunker
from financial_rag.core.errors import FinancialRAGError, RuntimeBootstrapError
from financial_rag.domain.fingerprints import fingerprint_model
from financial_rag.domain.retrieval import RetrievalConfig
from financial_rag.evaluation.runner import EvaluationRunner
from financial_rag.generation.context import ContextAssembler
from financial_rag.generation.openai_adapter import (
    OpenAIGenerationConfig,
    OpenAIResponsesAdapter,
)
from financial_rag.generation.protocols import GenerationAdapter
from financial_rag.generation.service import GroundedGenerationService
from financial_rag.indexing.service import CorpusIndexingService
from financial_rag.indexing.staging import UploadStagingService
from financial_rag.ingestion.service import FolderIngestionService
from financial_rag.retrieval.embeddings import BgeM3EmbeddingProvider
from financial_rag.retrieval.protocols import EmbeddingProvider, Reranker
from financial_rag.retrieval.rerankers import BgeM3Reranker
from financial_rag.retrieval.service import RetrievalService
from financial_rag.runtime.activation import RuntimeIndexActivator
from financial_rag.runtime.settings import LocalRuntimeConfig, LocalRuntimeSettings
from financial_rag.storage.database import create_database_engine, create_session_factory
from financial_rag.storage.job_store import PostgresCorpusBuildJobStore
from financial_rag.storage.revision_store import PostgresRevisionStore
from financial_rag.storage.settings import StorageSettings

logger = structlog.get_logger(__name__)
EXPECTED_ALEMBIC_HEAD = "20260812_0002"


class RuntimeComponentStatus(StrEnum):
    """Truthful startup state for an optional local component."""

    DISABLED = "disabled"
    CONFIGURED = "configured"
    VERIFIED = "verified"


class RuntimeReport(BaseModel):
    """Non-sensitive record of what the composition root actually configured."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_version: str
    retrieval: RuntimeComponentStatus
    generation: RuntimeComponentStatus
    evaluation: RuntimeComponentStatus
    revisions: RuntimeComponentStatus
    indexing: RuntimeComponentStatus
    database_smoke: RuntimeComponentStatus


@dataclass(slots=True)
class LocalRuntime:
    """Owned services and resources for one FastAPI lifespan."""

    container: ApiContainer
    report: RuntimeReport
    engine: AsyncEngine | None = None

    async def close(self) -> None:
        """Release resources created by the composition root."""
        if self.engine is not None:
            await self.engine.dispose()


EmbeddingFactory = Callable[[RetrievalConfig, LocalRuntimeConfig], EmbeddingProvider]
RerankerFactory = Callable[[RetrievalConfig, LocalRuntimeConfig], Reranker]
GenerationFactory = Callable[[LocalRuntimeSettings], GenerationAdapter]


def _default_embedding_factory(
    retrieval: RetrievalConfig, runtime: LocalRuntimeConfig
) -> EmbeddingProvider:
    return BgeM3EmbeddingProvider(
        model_identifier=retrieval.embedding_model_identifier,
        dimension=retrieval.embedding_dimension,
        device=runtime.embedding_device,
        batch_size=runtime.embedding_batch_size,
    )


def _default_reranker_factory(retrieval: RetrievalConfig, runtime: LocalRuntimeConfig) -> Reranker:
    return BgeM3Reranker(
        model_identifier=retrieval.reranker_model_identifier,
        device=runtime.embedding_device,
        batch_size=runtime.embedding_batch_size,
    )


def _default_generation_factory(settings: LocalRuntimeSettings) -> GenerationAdapter:
    if settings.openai_api_key is None:
        raise RuntimeBootstrapError("OPENAI_API_KEY is required for grounded generation.")
    return OpenAIResponsesAdapter(
        api_key=settings.openai_api_key,
        config=OpenAIGenerationConfig(
            model_identifier=settings.openai_model,
            timeout_seconds=settings.generation_timeout_seconds,
            max_retries=settings.generation_max_retries,
            max_output_tokens=settings.generation_max_output_tokens,
        ),
    )


async def verify_postgres_runtime(engine: AsyncEngine) -> None:
    """Verify connectivity, pgvector availability, and the expected Alembic head."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            vector_extension = await connection.scalar(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            migration_head = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    except Exception as exc:
        raise RuntimeBootstrapError("The optional PostgreSQL smoke check failed.") from exc
    if vector_extension != "vector":
        raise RuntimeBootstrapError("The PostgreSQL pgvector extension is not installed.")
    if migration_head != EXPECTED_ALEMBIC_HEAD:
        raise RuntimeBootstrapError("The PostgreSQL schema is not at the expected Alembic head.")


class LocalRuntimeBuilder:
    """Build services only from explicit settings; never at module import time."""

    def __init__(
        self,
        *,
        embedding_factory: EmbeddingFactory = _default_embedding_factory,
        reranker_factory: RerankerFactory = _default_reranker_factory,
        generation_factory: GenerationFactory = _default_generation_factory,
    ) -> None:
        self._embedding_factory = embedding_factory
        self._reranker_factory = reranker_factory
        self._generation_factory = generation_factory

    async def build(self, settings: LocalRuntimeSettings) -> LocalRuntime:
        """Compose configured local services and optionally verify PostgreSQL."""
        runtime_config = LocalRuntimeConfig.from_json_file(
            settings.project_path(settings.runtime_config_path)
        )
        retrieval_config = RetrievalConfig.from_json_file(
            settings.project_path(runtime_config.retrieval_config_path)
        )
        retrieval_service = self._build_retrieval(
            settings, runtime_config, retrieval_config=retrieval_config
        )
        generation_adapter = (
            self._generation_factory(settings) if settings.openai_api_key is not None else None
        )
        generation_service: GroundedGenerationService | None = None
        if retrieval_service is not None and generation_adapter is not None:
            generation_service = GroundedGenerationService(
                retrieval=retrieval_service,
                generator=generation_adapter,
                context_assembler=ContextAssembler(runtime_config.generation_context),
            )
        evaluation_service: EvaluationRunner | None = None
        if retrieval_service is not None:
            evaluation_service = EvaluationRunner(
                retrieval=retrieval_service,
                generation=generation_service,
                corpus_fingerprint=retrieval_service.manifest.chunk_mapping_fingerprint,
            )
        engine: AsyncEngine | None = None
        revisions: PostgresRevisionStore | None = None
        indexing_service: CorpusIndexingService | None = None
        database_smoke = RuntimeComponentStatus.DISABLED
        container = ApiContainer(
            retrieval=retrieval_service,
            generation=generation_service,
            evaluation=evaluation_service,
        )
        try:
            if settings.database_enabled:
                assert settings.database_url is not None
                storage_settings = StorageSettings(
                    database_url=settings.database_url,
                    database_echo=settings.database_echo,
                )
                engine = create_database_engine(storage_settings)
                session_factory = create_session_factory(engine)
                revisions = PostgresRevisionStore(session_factory)
                jobs = PostgresCorpusBuildJobStore(session_factory)
                database_smoke = RuntimeComponentStatus.CONFIGURED
                if settings.database_smoke_on_startup:
                    await verify_postgres_runtime(engine)
                    database_smoke = RuntimeComponentStatus.VERIFIED
                await jobs.fail_interrupted_jobs()
                indexing_embedder = self._embedding_factory(retrieval_config, runtime_config)
                indexing_reranker = (
                    self._reranker_factory(retrieval_config, runtime_config)
                    if runtime_config.reranker_enabled
                    else None
                )
                activator = RuntimeIndexActivator(
                    container=container,
                    revisions=revisions,
                    embedding_provider=indexing_embedder,
                    retrieval_config=retrieval_config,
                    reranker=indexing_reranker,
                    generation_adapter=generation_adapter,
                    context_config=runtime_config.generation_context,
                )
                indexing_service = CorpusIndexingService(
                    jobs=jobs,
                    revisions=revisions,
                    embedder=indexing_embedder,
                    retrieval_config=retrieval_config,
                    ingestion=FolderIngestionService(),
                    chunker=MarkdownChunker(runtime_config.chunking),
                    staging=UploadStagingService(
                        settings.project_path(settings.upload_staging_directory)
                    ),
                    activator=activator,
                    embedding_batch_size=runtime_config.embedding_batch_size,
                )
                container.revisions = revisions
                container.indexing = indexing_service
        except Exception:
            if engine is not None:
                await engine.dispose()
            raise

        report = RuntimeReport(
            runtime_version=runtime_config.runtime_version,
            retrieval=(
                RuntimeComponentStatus.CONFIGURED
                if retrieval_service is not None
                else RuntimeComponentStatus.DISABLED
            ),
            generation=(
                RuntimeComponentStatus.CONFIGURED
                if generation_service is not None
                else RuntimeComponentStatus.DISABLED
            ),
            evaluation=(
                RuntimeComponentStatus.CONFIGURED
                if evaluation_service is not None
                else RuntimeComponentStatus.DISABLED
            ),
            revisions=(
                RuntimeComponentStatus.CONFIGURED
                if revisions is not None
                else RuntimeComponentStatus.DISABLED
            ),
            indexing=(
                RuntimeComponentStatus.CONFIGURED
                if indexing_service is not None
                else RuntimeComponentStatus.DISABLED
            ),
            database_smoke=database_smoke,
        )
        logger.info("local_runtime_composed", **report.model_dump(mode="json"))
        return LocalRuntime(
            container=container,
            report=report,
            engine=engine,
        )

    def _build_retrieval(
        self,
        settings: LocalRuntimeSettings,
        runtime_config: LocalRuntimeConfig,
        *,
        retrieval_config: RetrievalConfig,
    ) -> RetrievalService | None:
        artifact_directory = settings.retrieval_artifact_directory
        if artifact_directory is None:
            return None
        try:
            embedding_provider = self._embedding_factory(retrieval_config, runtime_config)
            reranker = (
                self._reranker_factory(retrieval_config, runtime_config)
                if runtime_config.reranker_enabled
                else None
            )
            return RetrievalService.load_artifacts(
                settings.project_path(artifact_directory),
                embedding_provider=embedding_provider,
                config=retrieval_config,
                chunking_configuration_fingerprint=fingerprint_model(runtime_config.chunking),
                reranker=reranker,
            )
        except FinancialRAGError as exc:
            raise RuntimeBootstrapError(
                "Configured retrieval artifacts could not be loaded safely."
            ) from exc
        except ValueError as exc:
            raise RuntimeBootstrapError(
                "Configured retrieval settings or artifacts are incompatible."
            ) from exc
