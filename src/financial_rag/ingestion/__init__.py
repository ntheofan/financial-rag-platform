"""Local, offline document ingestion adapters and services."""

from financial_rag.ingestion.loaders import PyMuPDFLoader, TextMarkdownLoader
from financial_rag.ingestion.normalization import normalize_document_text
from financial_rag.ingestion.service import FolderIngestionService

__all__ = [
    "FolderIngestionService",
    "PyMuPDFLoader",
    "TextMarkdownLoader",
    "normalize_document_text",
]
