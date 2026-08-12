"""Bounded server-owned staging for local document uploads."""

import shutil
from dataclasses import dataclass
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field

from financial_rag.core.errors import UploadPolicyError
from financial_rag.domain.indexing import CorpusBuildJobId, UploadDocument
from financial_rag.domain.metadata import SourceMetadata
from financial_rag.ingestion.base import MetadataProvider

logger = structlog.get_logger(__name__)
SUPPORTED_UPLOAD_EXTENSIONS = frozenset({".md", ".pdf", ".txt"})


class UploadPolicy(BaseModel):
    """Explicit local-demo limits applied before writing staging files."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_files: int = Field(default=10, ge=1, le=10)
    max_file_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    max_total_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    supported_extensions: frozenset[str] = SUPPORTED_UPLOAD_EXTENSIONS


@dataclass(frozen=True, slots=True)
class StagedUploadBatch:
    """Server-owned paths plus portable source labels for one job."""

    job_id: CorpusBuildJobId
    folder: Path
    source_names: tuple[tuple[str, str], ...]

    @property
    def metadata_provider(self) -> MetadataProvider:
        """Create metadata without exposing server-generated staging names."""
        source_by_staged_name = dict(self.source_names)

        def provide(_path: Path, relative_path: Path) -> SourceMetadata:
            try:
                source_file = source_by_staged_name[relative_path.as_posix()]
            except KeyError as exc:
                raise UploadPolicyError("Staged upload mapping is incomplete.") from exc
            return SourceMetadata(source_file=source_file)

        return provide


class UploadStagingService:
    """Write validated uploads only below an explicit ignored local root."""

    def __init__(self, root: Path, *, policy: UploadPolicy | None = None) -> None:
        self._root = root
        self.policy = policy or UploadPolicy()

    def stage(
        self,
        job_id: CorpusBuildJobId,
        uploads: tuple[UploadDocument, ...],
    ) -> StagedUploadBatch:
        """Validate names/sizes and create one isolated non-overwriting batch."""
        if not uploads:
            raise UploadPolicyError("At least one document is required.")
        if len(uploads) > self.policy.max_files:
            raise UploadPolicyError(f"At most {self.policy.max_files} documents are allowed.")

        normalized_names: set[str] = set()
        total_bytes = 0
        for upload in uploads:
            self._validate_filename(upload.filename)
            normalized = upload.filename.casefold()
            if normalized in normalized_names:
                raise UploadPolicyError("Uploaded document names must be unique.")
            normalized_names.add(normalized)
            if len(upload.content) > self.policy.max_file_bytes:
                raise UploadPolicyError("One uploaded document exceeds the per-file limit.")
            total_bytes += len(upload.content)
        if total_bytes > self.policy.max_total_bytes:
            raise UploadPolicyError("Uploaded documents exceed the total request limit.")

        root = self._root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        folder = root / job_id
        try:
            folder.mkdir(mode=0o700, exist_ok=False)
            source_names: list[tuple[str, str]] = []
            for position, upload in enumerate(uploads, start=1):
                staged_name = f"{position:02d}{Path(upload.filename).suffix.lower()}"
                (folder / staged_name).write_bytes(upload.content)
                source_names.append((staged_name, upload.filename))
        except OSError as exc:
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            raise UploadPolicyError("Unable to create the local upload staging batch.") from exc

        logger.info(
            "upload_batch_staged",
            job_id=job_id,
            file_count=len(uploads),
            total_bytes=total_bytes,
        )
        return StagedUploadBatch(
            job_id=job_id,
            folder=folder,
            source_names=tuple(source_names),
        )

    def cleanup(self, batch: StagedUploadBatch) -> None:
        """Remove only the exact server-generated batch owned by this service."""
        root = self._root.resolve()
        folder = batch.folder.resolve()
        if folder.parent != root or folder.name != batch.job_id:
            raise UploadPolicyError("Refusing to clean an invalid staging path.")
        if folder.exists():
            shutil.rmtree(folder)
        logger.info("upload_batch_removed", job_id=batch.job_id)

    def _validate_filename(self, filename: str) -> None:
        if filename in {".", ".."} or "/" in filename or "\\" in filename:
            raise UploadPolicyError("Uploaded filenames cannot contain paths.")
        if any(ord(character) < 32 for character in filename):
            raise UploadPolicyError("Uploaded filenames contain invalid control characters.")
        suffix = Path(filename).suffix.lower()
        if suffix not in self.policy.supported_extensions:
            supported = ", ".join(sorted(self.policy.supported_extensions))
            raise UploadPolicyError(f"Unsupported upload type. Allowed extensions: {supported}.")
