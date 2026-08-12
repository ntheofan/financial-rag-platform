# Phase 10 release-candidate validation

## Purpose

Phase 10 freezes a small, reviewable validation boundary for the local
single-user recruiter demo. It does not introduce a feature, publish a release,
claim production readiness, or approve public deployment.

The checked-in `platform_rc_v1` contract records the expected development
status, package and protocol versions, current Alembic head, OpenAPI path set,
local notebook inventory boundary, and required gate names. The contract contains no environment
result and therefore cannot become stale evidence that a check passed.

## Offline end-to-end proof

`tests/e2e/test_synthetic_recruiter_flow.py` exercises the real HTTP and service
composition with one generated in-memory Markdown filing:

1. multipart upload and bounded server-owned staging;
2. local text loading, normalization, Markdown-aware chunking, and lineage;
3. deterministic fake embeddings and an in-memory immutable revision adapter;
4. index compatibility validation and process-local activation;
5. dense retrieval, hybrid retrieval, and hybrid plus fake reranking;
6. top-five context assembly and citation validation with a fake generator;
7. a complete paired `platform_eval_v1` retrieval evaluation.

The test performs no network call and uses no PostgreSQL, pgvector, OpenAI API,
BGE model, source PDF, FinanceBench row, or persisted corpus artifact. Its
in-memory revision adapter is test-only and is not presented as persistence
validation.

## Safe source preflight

Run:

```powershell
.\.venv\Scripts\python.exe scripts/check_release_candidate.py
```

The command checks deterministic source properties and reports whether local
Docker, database configuration, and the optional model package are present. It
does not connect to any service, load model weights, read `.env` values, or emit
credential values. Missing infrastructure is reported as `unavailable`.

Notebook inventory accepts exactly two public-policy states: all 15 immutable
artifacts in the local research worktree, or zero `.ipynb` files in a clean
public clone. A partial inventory fails. The public boundary continues to block
the notebooks until their separate manual publication review is complete.

Use the following only when the machine is intentionally prepared for the full
local validation path:

```powershell
.\.venv\Scripts\python.exe scripts/check_release_candidate.py --require-infrastructure
```

This strict mode makes absent prerequisites fail the preflight. It does not
replace the actual commands below.

## Full local release-candidate sequence

On a machine with Python 3.12, Docker Desktop/Engine, model access, and a local
ignored `.env`:

```powershell
py -3.12 -m pip install -e ".[demo,models,dev,security]"
.\.venv\Scripts\python.exe scripts/check_publication.py
.\.venv\Scripts\python.exe scripts/check_release_candidate.py --require-infrastructure
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
.\.venv\Scripts\python.exe -m pip_audit --strict .
docker compose config --quiet
docker compose up --build --wait
docker compose ps
docker compose down
```

Then use only synthetic or separately cleared documents to verify a real
model-enabled corpus build, activation, retrieval comparison, grounded answer,
and evaluation through the Streamlit UI. Do not capture or publish document
text, chunk content, prompts, answers, vectors, database contents, or secrets as
evidence.

## Evidence still required before a public source release

- a successful PostgreSQL 17/pgvector migration and integration run;
- a successful model-enabled synthetic index build and activation;
- a successful Compose startup/readiness/shutdown cycle;
- a successful strict dependency audit in a supported environment;
- a successful GitHub Actions run on the exact commit;
- manual notebook hash comparison against an approved baseline;
- manual staged-diff, attribution, claim, screenshot, and artifact review.

Public deployment remains explicitly out of scope.
