# v0.1.0 release notes - draft, not released

`financial-rag-platform` is an in-development local single-user portfolio demo
for transparent financial-document retrieval and grounded answers.

## Included

- deterministic PDF/Markdown/text ingestion and Markdown-aware chunking;
- full document/chunk metadata lineage and stable identifiers;
- Dense, Hybrid, and Hybrid + Reranker `platform_v1` retrieval;
- immutable PostgreSQL/pgvector corpus and index revision design;
- FastAPI contracts, local Streamlit client, grounded citations, and paired
  `platform_eval_v1` evaluation;
- bounded local upload/index activation workflow;
- offline synthetic tests, public-boundary scanning, Docker/Compose definitions,
  Alembic migrations, and GitHub Actions gates;
- Phase 11 loopback-only real-service acceptance tooling.

## Evidence boundary

The checked-in test suite and source gates are not evidence that Docker,
PostgreSQL, BGE models, OpenAI, or GitHub Actions passed on the release commit.
These notes must remain draft until every blocking item in
`docs/release-checklist.md` is recorded as passed for the exact commit.

No FinanceBench score, production readiness, public deployment, or performance
claim is included.

## Known limitations

- local single-user only;
- no authentication, public ingress, multi-user isolation, distributed jobs,
  managed storage, autoscaling, or service-level objective;
- text-only PDF extraction with no OCR claim and limited table fidelity;
- in-process, non-resumable corpus-build jobs;
- model downloads and OpenAI usage require separate local configuration;
- thesis notebooks remain local immutable research artifacts pending separate
  public-content review.

## Release blockers

- successful real local acceptance;
- successful strict dependency audit;
- clean exact-commit repository gate;
- successful GitHub Actions run on that commit;
- explicit approval of the notebook hash snapshot and publication boundary;
- final manual claim, attribution, staged-diff, and screenshot review.
