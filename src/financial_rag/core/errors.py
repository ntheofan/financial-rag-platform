"""Domain-specific errors for local document ingestion and chunking."""

from pathlib import Path


class FinancialRAGError(Exception):
    """Base class for expected platform errors."""


class RuntimeBootstrapError(FinancialRAGError):
    """Raised when an explicitly configured local runtime cannot be composed."""


class GenerationError(FinancialRAGError):
    """Base class for grounded answer-generation failures."""


class CitationValidationError(GenerationError):
    """Raised when a generated answer cannot be linked to supplied contexts."""


class GenerationProviderError(GenerationError):
    """Raised when the configured generation provider fails safely."""


class EvaluationError(FinancialRAGError):
    """Base class for benchmark import and evaluation failures."""


class BenchmarkImportError(EvaluationError):
    """Raised when a local benchmark file is unsafe, malformed, or unsupported."""


class IngestionError(FinancialRAGError):
    """Base class for local ingestion failures."""


class DocumentNotFoundError(IngestionError):
    """Raised when an input path does not identify an existing file."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Document does not exist or is not a file: {path}")


class InputFolderError(IngestionError):
    """Raised when an ingestion folder is missing or invalid."""


class EmptyInputError(IngestionError):
    """Raised when a file or folder contains no ingestible content."""


class UnsupportedDocumentTypeError(IngestionError):
    """Raised when a path has no registered local loader."""

    def __init__(self, path: Path, supported_extensions: tuple[str, ...]) -> None:
        supported = ", ".join(supported_extensions)
        super().__init__(
            f"Unsupported document type '{path.suffix or '<none>'}' for {path.name}. "
            f"Supported extensions: {supported}."
        )


class CorruptDocumentError(IngestionError):
    """Raised when a supported document cannot be decoded or parsed."""


class ChunkingError(FinancialRAGError):
    """Raised when validated source documents cannot produce valid chunks."""


class RetrievalError(FinancialRAGError):
    """Base class for expected indexing and retrieval failures."""


class EmptyCorpusError(RetrievalError):
    """Raised when indexing is requested without any chunks."""


class EmptyQueryError(RetrievalError):
    """Raised when retrieval is requested with a blank query."""


class InvalidEmbeddingError(RetrievalError):
    """Raised when vectors have an invalid shape, dimension, or norm."""


class DuplicateChunkError(RetrievalError):
    """Raised when a corpus or candidate list contains conflicting chunk IDs."""


class ManifestCompatibilityError(RetrievalError):
    """Raised when persisted index metadata is incompatible with runtime settings."""


class RetrievalArtifactError(RetrievalError):
    """Raised when local index artifacts are missing, corrupt, or misaligned."""


class ProviderUnavailableError(RetrievalError):
    """Raised when an optional local model provider cannot be loaded."""


class RerankerRequiredError(RetrievalError):
    """Raised when V3 is requested without a configured reranker."""


class StorageError(FinancialRAGError):
    """Base class for expected persistence failures."""


class StorageConfigurationError(StorageError):
    """Raised when database settings are missing or unsafe."""


class RevisionNotFoundError(StorageError):
    """Raised when a requested corpus or index revision does not exist."""


class RevisionConflictError(StorageError):
    """Raised when an immutable persisted identity has conflicting content."""


class RevisionCompatibilityError(StorageError):
    """Raised when corpus, manifest, and vector revisions are incompatible."""


class CorpusBuildError(FinancialRAGError):
    """Base class for bounded local corpus-build failures."""


class CorpusBuildJobNotFoundError(CorpusBuildError):
    """Raised when a corpus-build job identifier is unknown."""


class CorpusBuildTransitionError(CorpusBuildError):
    """Raised when a durable job state transition is invalid or concurrent."""


class UploadPolicyError(CorpusBuildError):
    """Raised when local upload metadata or size violates the staging policy."""
