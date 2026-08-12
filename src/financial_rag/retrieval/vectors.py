"""Pure dense-vector validation, normalization, and fingerprinting."""

import hashlib

import numpy as np
from numpy.typing import ArrayLike, NDArray

from financial_rag.core.errors import InvalidEmbeddingError
from financial_rag.domain.fingerprints import ConfigurationFingerprint


def normalize_l2(vectors: ArrayLike, *, dimension: int) -> NDArray[np.float32]:
    """Validate a two-dimensional matrix and return unit-length float32 rows."""
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2:
        raise InvalidEmbeddingError("Embedding matrix must be two-dimensional")
    if matrix.shape[1] != dimension:
        raise InvalidEmbeddingError(
            f"Embedding dimension mismatch: expected {dimension}, got {matrix.shape[1]}"
        )
    if not np.isfinite(matrix).all():
        raise InvalidEmbeddingError("Embedding matrix contains non-finite values")

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise InvalidEmbeddingError("Embedding vectors must have non-zero L2 norm")
    return np.ascontiguousarray(matrix / norms, dtype=np.float32)


def normalize_query_vector(vector: ArrayLike, *, dimension: int) -> NDArray[np.float32]:
    """Validate and normalize a single vector as a one-row matrix."""
    array = np.asarray(vector, dtype=np.float32)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.shape[0] != 1:
        raise InvalidEmbeddingError("Query embedding must contain exactly one vector")
    return normalize_l2(array, dimension=dimension)


def fingerprint_vector_matrix(vectors: ArrayLike, *, dimension: int) -> ConfigurationFingerprint:
    """Hash normalized float32 rows using the Phase 2 FAISS manifest format."""
    matrix = normalize_l2(vectors, dimension=dimension)
    digest = hashlib.sha256()
    digest.update(f"float32:{matrix.shape[0]}:{dimension}".encode("ascii"))
    digest.update(matrix.tobytes())
    return ConfigurationFingerprint(value=digest.hexdigest())
