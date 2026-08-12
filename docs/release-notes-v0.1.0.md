# Release notes - v0.1.0

`financial-rag-platform` is an in-development, local single-user portfolio demo
for financial-document intelligence. This is its first source release; it is
not a deployment or production-readiness announcement.

## Highlights

- Local PDF, Markdown, and text ingestion with deterministic metadata lineage.
- Dense, hybrid, and hybrid-plus-reranker retrieval under the versioned
  `platform_v1` comparison protocol.
- Grounded OpenAI generation with validated citations, retrieved chunks, and
  component score traces.
- PostgreSQL/pgvector corpus and index revisions with SQLAlchemy 2 and Alembic.
- FastAPI composition and a five-view Streamlit recruiter demo.
- Paired Hit@K and MRR evaluation through a versioned benchmark contract.
- Docker Compose packaging, strict typed/tested source gates, publication
  scanning, dependency auditing, and green hosted CI.

## Checked demo inputs

The public walkthrough uses only original synthetic project fixtures:

- `tests/fixtures/demo/acme-2025-10k.md`;
- `tests/fixtures/demo/acme-benchmark.json`.

The benchmark relevance IDs are regenerated and checked against the synthetic
document during automated tests. They are not FinanceBench examples or scores.

## Honest boundaries

- Local and single-user only; no authentication or tenant isolation.
- In-process indexing jobs are not resumable workers.
- PDF extraction is text-only, without OCR or complete table-fidelity claims.
- No public deployment, managed persistence, monitoring/SLO, or scaling claim.
- No source filing, FinanceBench data, generated context, vector index, local
  database, model cache, `.env`, or secret is included.
- No financial correctness or benchmark-superiority claim is made.

## Verification status

The release-candidate source, container, PostgreSQL/pgvector, real local
synthetic workflow, publication boundary, and hosted CI are checked separately.
The exact local Phase 14 evidence is recorded in `docs/phase-14-report.md`. A
GitHub Release is created only after hosted CI passes on the exact source
commit.
