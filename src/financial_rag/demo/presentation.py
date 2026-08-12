"""Pure presentation helpers shared by Streamlit rendering and unit tests."""

from pydantic import BaseModel, ConfigDict

from financial_rag.domain.retrieval import RetrievedChunk


class ScoreDisplay(BaseModel):
    """One available retrieval score formatted without changing its value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    value: float


def source_label(chunk: RetrievedChunk) -> str:
    """Build a concise source label from available lineage fields."""
    parts = [chunk.source_file]
    if chunk.page_number is not None:
        parts.append(f"page {chunk.page_number}")
    if chunk.section_heading:
        parts.append(chunk.section_heading)
    return " · ".join(parts)


def available_scores(chunk: RetrievedChunk) -> tuple[ScoreDisplay, ...]:
    """Expose only score families actually produced by the selected mode."""
    values = (
        ("Dense", chunk.dense_score),
        ("BM25", chunk.bm25_score),
        ("RRF", chunk.rrf_score),
        ("Reranker", chunk.rerank_score),
    )
    return tuple(
        ScoreDisplay(label=label, value=value) for label, value in values if value is not None
    )


def top_chunk_overlap(left: tuple[RetrievedChunk, ...], right: tuple[RetrievedChunk, ...]) -> float:
    """Return Jaccard overlap of returned chunk IDs, with a defined empty case."""
    left_ids = {chunk.chunk_id for chunk in left}
    right_ids = {chunk.chunk_id for chunk in right}
    if not left_ids and not right_ids:
        return 1.0
    return len(left_ids & right_ids) / len(left_ids | right_ids)
