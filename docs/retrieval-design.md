# Retrieval design — `platform_v1`

## Scope and comparison routes

The retrieval layer consumes validated in-memory chunks produced by ingestion and stops
at ranked retrieval output:

```text
Ingestion chunks
      |
      +--> L2-normalized embeddings --> FAISS IndexFlatIP --+--> V1 dense
      |                                                     |
query --> versioned finance expansion ----------------------+
      |                                                     |
      +--> BM25 --------------------------------------------+--> weighted RRF --> V2 hybrid
                                                                     |
                                                                     +--> cross-encoder --> V3 hybrid_reranked
```

All routes are document-unknown: they search the complete indexed chunk
collection. There is no expected-document filter or benchmark-label leakage.
The service returns at most ten chunks by default. It does not assemble the
top-five generation context, call an LLM, generate an answer, or compute an
evaluation metric.

## Dense retrieval (V1)

The protocol identifies `BAAI/bge-m3`, 1,024 dimensions, and L2 normalization.
The FAISS adapter validates every matrix and query vector for shape, dimension,
finite values, and non-zero norm, then normalizes it again at the index boundary.
Metadata and vector rows share one immutable ordered chunk mapping.

For two unit-length vectors `x` and `y`:

```text
x · y = ||x|| ||y|| cos(theta) = cos(theta)
```

Therefore `IndexFlatIP` inner-product ranking over L2-normalized vectors is the
same ordering as cosine-similarity ranking. `IndexFlatIP` is exact flat search;
The retrieval layer makes no approximate-index or scaling claim. Equal scores are stabilized
by `chunk_id`.

V1 searches the entire FAISS index and returns `final_top_k=10` by default. Each
result exposes `dense_rank` and `dense_score` plus the complete source metadata.

## Lexical BM25

The BM25 adapter preserves the transparent notebook implementation instead of
adding a library whose IDF edge behavior could differ. It uses:

- token pattern `[a-zA-Z0-9&\.]+`;
- `k1=1.5`;
- `b=0.75`;
- positive IDF `log(1 + (N - df + 0.5) / (df + 0.5))`.

It returns no hits when no query token occurs in the corpus. Score ties use
`chunk_id`. The ASCII tokenizer is thesis-compatible but is a known limitation
for multilingual or punctuation-heavy filings.

## Hybrid retrieval (V2)

V2 obtains 20 dense candidates and 10 BM25 candidates from the same complete
corpus. Duplicate `chunk_id` values are merged. A duplicate inside one source
contributes only once; conflicting row mappings fail explicitly.

Weighted Reciprocal Rank Fusion uses:

```text
RRF(d) = 1.0 / (30 + dense_rank(d))
       + 0.2 / (30 + bm25_rank(d))
```

A missing component contributes zero. Fusion does not mix incomparable raw
dense and BM25 scores. Ordering is deterministic by descending RRF score,
best component rank, then `chunk_id`. V2 keeps the first ten fused candidates
and exposes every applicable component rank/score and the final `rrf_score`.

## Hybrid plus reranking (V3)

V3 builds the same full hybrid union as V2 and sends every unique union
candidate—not an already truncated top-ten list—to the configured cross-encoder.
The default identifier is `BAAI/bge-reranker-v2-m3`. Reranker scores determine
the final order; the previous RRF order and `chunk_id` stabilize equal scores.
Only then does V3 keep the final top ten.

`BgeM3Reranker` is a lazy FlagEmbedding adapter. Its constructor does not import
FlagEmbedding, initialize a model, access the network, or select a GPU. Actual
weight loading occurs only when the caller explicitly invokes scoring after
installing the optional `models` extra. Automated tests use `FakeReranker`.

## Query expansion

`configs/retrieval/platform_v1.json` contains the migrated finance alias rules
under version `finance_aliases_v1`. Queries are lowercased and whitespace is
collapsed. Matching rules run longest-alias-first; expansions preserve declared
order and are de-duplicated deterministically.

The map includes the thesis aliases for PPE, CAPEX, COGS, EBITDA, OPEX, margins,
cash flow, working capital, payout/retention ratios, statement names, and year
end. Expansion is part of the retrieval configuration fingerprint and can be
disabled explicitly for a controlled ablation.

## Contracts and score transparency

`RetrievedChunk` retains:

- `document_id`, `source_file`, `company`, `filing_type`, `filing_date`;
- `page_number`, `section_heading`, `chunk_id`, `chunk_index`;
- exact chunk `content` and final `rank`;
- optional `dense_rank`, `dense_score`, `bm25_rank`, `bm25_score`, `rrf_score`,
  and `rerank_score`.

`RetrievalResult` records the original query, expanded query, selected mode,
`document_unknown=true`, the immutable retrieval configuration fingerprint, and
contiguous one-based results.

## Manifest and artifact compatibility

An indexing run creates a manifest containing:

- `platform_version`;
- embedding model identifier and dimension;
- normalization method;
- chunking configuration fingerprint;
- ordered chunk-mapping fingerprint;
- FAISS vector fingerprint;
- corpus/chunk count;
- retrieval configuration fingerprint;
- timezone-aware creation timestamp;
- artifact format/version.

Local save/load writes a FAISS index, chunk mapping, and JSON manifest only at an
explicit `pathlib.Path`. Generated filenames are ignored by Git. Load rejects a
mismatched embedding model, dimension, normalization method, chunking
fingerprint, ordered mapping fingerprint, count, or FAISS dimension.

Changing only BM25/RRF/query-expansion settings does not alter dense vectors, but
the manifest still records the original retrieval configuration fingerprint for
traceability. A future comparison runner must decide explicitly whether to reuse
such an embedding-compatible index under a new retrieval configuration.

## Thesis parameters versus new engineering work

Migrated thesis-compatible choices are BGE-M3, 1,024 dimensions, normalized
`IndexFlatIP`, BM25 `1.5/0.75`, candidate counts `20/10`, weighted RRF
`k=30` and weights `1.0/0.2`, the finance alias logic, document-unknown search,
and the BGE reranker identifier.

New `platform_v1` engineering includes typed provider ports, strict Pydantic
contracts, deterministic fake providers, stable tie-breaking, duplicate
handling, complete metadata lineage, corrected full-pool reranking, immutable
fingerprints, artifact compatibility gates, pathlib-only persistence paths, and
structured logs.

These choices make the implementation testable; they do not prove reproduction
of the historical metrics. Those results remain `research_legacy_v1`. No real
corpus indexing, full BGE/reranker execution, answers, or new evaluation metrics
are produced by the retrieval layer.
