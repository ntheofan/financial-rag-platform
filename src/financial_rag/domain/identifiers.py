"""Deterministic, content-derived identifiers for documents and chunks."""

import hashlib
import json


def make_document_id(content: bytes) -> str:
    """Return a stable document identifier derived from the original file bytes."""
    return f"doc_{hashlib.sha256(content).hexdigest()[:32]}"


def make_chunk_id(
    *,
    document_id: str,
    chunk_index: int,
    page_number: int | None,
    section_heading: str | None,
    content: str,
) -> str:
    """Return a stable identifier derived from chunk content and its lineage."""
    identity = {
        "content": content,
        "document_id": document_id,
        "page_number": page_number,
        "section_heading": section_heading,
        "chunk_index": chunk_index,
    }
    serialized = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"chunk_{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:32]}"
