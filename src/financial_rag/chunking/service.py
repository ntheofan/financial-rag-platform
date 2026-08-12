"""Markdown-aware recursive chunking with complete metadata lineage."""

from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import ValidationError

from financial_rag.chunking.sections import section_heading_at
from financial_rag.core.errors import ChunkingError
from financial_rag.domain.chunking import ChunkingConfig
from financial_rag.domain.identifiers import make_chunk_id
from financial_rag.domain.metadata import ChunkMetadata, DocumentMetadata
from financial_rag.ingestion.normalization import normalize_document_text

logger = structlog.get_logger(__name__)


def _langchain_metadata(metadata: ChunkMetadata) -> dict[str, Any]:
    return metadata.model_dump(mode="json")


class MarkdownChunker:
    """Create deterministic chunks while retaining page and source lineage."""

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        *,
        splitter: RecursiveCharacterTextSplitter | None = None,
    ) -> None:
        self.config = config or ChunkingConfig()
        self._splitter = splitter or RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=list(self.config.separators),
            keep_separator=True,
            add_start_index=True,
            length_function=len,
            is_separator_regex=False,
        )

    def chunk_documents(self, documents: Sequence[Document]) -> list[Document]:
        """Chunk normalized LangChain documents and validate all output metadata."""
        if not documents:
            raise ChunkingError("At least one source document is required")

        next_chunk_index: dict[str, int] = {}
        chunks: list[Document] = []
        for source_document in documents:
            try:
                source_metadata = DocumentMetadata.model_validate(source_document.metadata)
            except ValidationError as exc:
                raise ChunkingError("Source document metadata is invalid") from exc

            content = normalize_document_text(source_document.page_content)
            if not content:
                raise ChunkingError(
                    f"Source document contains no normalized text: {source_metadata.source_file}"
                )

            split_documents = self._splitter.create_documents([content])
            for split_document in split_documents:
                chunk_text = split_document.page_content.strip()
                if len(chunk_text) < self.config.min_chunk_chars:
                    continue

                start_index_value = split_document.metadata.get("start_index", 0)
                if not isinstance(start_index_value, int):
                    raise ChunkingError("Text splitter returned an invalid start_index")

                chunk_index = next_chunk_index.get(source_metadata.document_id, 0)
                section_heading = section_heading_at(
                    content,
                    start_index_value,
                    default=source_metadata.section_heading,
                )
                chunk_id = make_chunk_id(
                    document_id=source_metadata.document_id,
                    chunk_index=chunk_index,
                    page_number=source_metadata.page_number,
                    section_heading=section_heading,
                    content=chunk_text,
                )
                chunk_metadata = ChunkMetadata(
                    document_id=source_metadata.document_id,
                    source_file=source_metadata.source_file,
                    company=source_metadata.company,
                    filing_type=source_metadata.filing_type,
                    filing_date=source_metadata.filing_date,
                    page_number=source_metadata.page_number,
                    section_heading=section_heading,
                    chunk_id=chunk_id,
                    chunk_index=chunk_index,
                )
                chunks.append(
                    Document(page_content=chunk_text, metadata=_langchain_metadata(chunk_metadata))
                )
                next_chunk_index[source_metadata.document_id] = chunk_index + 1

        if not chunks:
            raise ChunkingError(
                "No chunks met the configured minimum length "
                f"({self.config.min_chunk_chars} characters)"
            )

        logger.info(
            "documents_chunked",
            source_document_count=len(documents),
            unique_document_count=len(next_chunk_index),
            chunk_count=len(chunks),
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )
        return chunks
