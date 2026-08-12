"""Synthetic Phase 1 chunks and platform_v1 test configuration."""

from datetime import date
from pathlib import Path

from langchain_core.documents import Document

from financial_rag.domain.identifiers import make_chunk_id, make_document_id
from financial_rag.domain.metadata import ChunkMetadata
from financial_rag.domain.retrieval import RetrievalConfig

PROJECT_ROOT = Path(__file__).parents[3]
PLATFORM_CONFIG_PATH = PROJECT_ROOT / "configs" / "retrieval" / "platform_v1.json"


def fake_retrieval_config(
    *,
    dimension: int = 128,
    final_top_k: int = 3,
    dense_candidate_count: int = 4,
    bm25_candidate_count: int = 4,
) -> RetrievalConfig:
    """Adapt the versioned protocol only to the deterministic fake provider."""
    base = RetrievalConfig.from_json_file(PLATFORM_CONFIG_PATH)
    return base.model_copy(
        update={
            "embedding_model_identifier": "fake-hash-v1",
            "embedding_dimension": dimension,
            "reranker_model_identifier": "fake-reranker-v1",
            "final_top_k": final_top_k,
            "dense_candidate_count": dense_candidate_count,
            "bm25_candidate_count": bm25_candidate_count,
        }
    )


def synthetic_chunks(texts: list[str]) -> list[Document]:
    """Create valid in-memory chunks without writing dataset artifacts."""
    document_id = make_document_id(b"synthetic retrieval filing")
    documents: list[Document] = []
    for index, text in enumerate(texts):
        section = f"Synthetic Section {index + 1}"
        metadata = ChunkMetadata(
            document_id=document_id,
            source_file="synthetic/acme-2025-10k.md",
            company="ACME Corp",
            filing_type="10-K",
            filing_date=date(2025, 12, 31),
            page_number=index + 1,
            section_heading=section,
            chunk_id=make_chunk_id(
                document_id=document_id,
                chunk_index=index,
                page_number=index + 1,
                section_heading=section,
                content=text,
            ),
            chunk_index=index,
        )
        documents.append(Document(page_content=text, metadata=metadata.model_dump(mode="json")))
    return documents
