# Phase 12 report - public baseline hardening

Date: 2026-08-12

## Outcome

Phase 12 is complete as a local release-engineering milestone. The project now
has a substantially smaller CPU-only model image, cache-efficient Docker build
stages, a stricter publication boundary, clean-stack PostgreSQL/pgvector and
real-service acceptance evidence, and a reviewed public-file baseline ready
for its first local Git commit.

The project remains **in development**. This phase does not claim public
deployment, production operations, scalability, authentication, or a published
FinanceBench result. No tag, push, GitHub release, or deployment was performed.

## Changes

### CPU-only and cache-efficient containers

- `Dockerfile` now separates foundation, dependency, and source layers for the
  API, model-enabled API, and Streamlit demo targets.
- The model target installs `torch==2.9.1` from the official PyTorch CPU wheel
  index before installing the remaining optional model dependencies.
- BuildKit pip cache mounts are used for all dependency-install layers.
- Source-only edits no longer invalidate the expensive model-dependency layer.
- The non-root UID/GID `10001` runtime and writable Hugging Face cache ownership
  remain enforced.
- `pyproject.toml` records the matching Torch version in the optional `models`
  extra while keeping the CPU index selection as an explicit Docker concern.
- Compose continues to select the model-enabled target. The Docker CI job now
  builds that real target rather than only the lightweight API target and uses
  GitHub Actions layer caching.

### Publication and configuration hardening

- `.gitignore`, `.dockerignore`, the publication scanner, and its tests reject
  generated archive formats (`.7z`, `.gz`, `.rar`, `.tar`, `.tgz`, `.zip`)
  unless a future policy explicitly allowlists one.
- The local duplicate `docs.zip` remains untouched and ignored; it is not part
  of the public baseline.
- Runtime/bootstrap tests isolate themselves from a developer's ignored
  `.env`, so automated tests cannot discover or call a local OpenAI key.
- Public/runtime OpenAI defaults use the thesis-compatible `gpt-4o-mini`
  identifier instead of an invalid placeholder. The ignored local key was
  never printed or copied.
- The PostgreSQL revision store flushes parent corpus/index rows before their
  dependent membership/vector rows. SQLite test foreign keys are enabled so
  the ordering regression is covered offline.
- Container-runtime, publication-policy, release-checklist, and README text now
  describe the CPU image path and archive boundary without adding production
  or benchmark claims.

Primary files updated for Phase 12:

- `Dockerfile`, `.dockerignore`, `.gitignore`, `pyproject.toml`, `compose.yaml`;
- `.pre-commit-config.yaml` and `tests/test_import_isolation.py`;
- `.env.example`, `configs/runtime/local_v1.json`;
- `.github/workflows/ci.yml`;
- `src/financial_rag/storage/revision_store.py` and runtime/OpenAI defaults;
- publication, container, storage, and runtime-isolation tests;
- `README.md`, `docs/container-runtime.md`, `docs/publication-policy.md`,
  `docs/release-checklist.md`, and this report.

## Verification

### Python environment and source suite

Commands:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo,dev,security]"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
$testTemp = Join-Path $env:TEMP ('financial-rag-pytest-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q -p no:cacheprovider --basetemp $testTemp
```

Actual results:

- editable install: passed;
- `pip check`: `No broken requirements found`;
- Ruff lint: `All checks passed!`;
- Ruff format: `191 files already formatted`;
- mypy: `Success: no issues found in 145 source files`;
- pytest: `233 passed, 1 skipped in 17.10s`;
- combined branch coverage: 87%;
- the skipped test is the deliberately opt-in host PostgreSQL integration
  test. The same integration test passed against the clean Linux stack below.

The global `python` command is not present in this PowerShell session. One
multi-command probe therefore reported `python` as unavailable even though the
later Ruff/mypy commands passed. It was immediately repeated with the explicit
`.venv` interpreter; that is the successful `pip check` result recorded above.

The full pre-commit configuration was also exercised from its ignored local
cache:

```powershell
$env:PRE_COMMIT_HOME = (Join-Path (Get-Location) '.cache\pre-commit')
.\.venv\Scripts\pre-commit.exe run --all-files
.\.venv\Scripts\pre-commit.exe run --hook-stage manual --all-files
```

The first isolated run exposed that the mypy hook had not installed project
dependencies. Its environment now declares the project check dependency set,
shared with the manual pytest hook. The manual pytest run then exposed a
subprocess test's reliance on a host editable install; the test now supplies
the repository `src` path explicitly. Final pre-commit result: Ruff lint,
Ruff format, mypy, pytest, and the publication boundary all passed.

### Publication and release contracts

Commands:

```powershell
.\.venv\Scripts\python.exe scripts\check_publication.py
.\.venv\Scripts\python.exe scripts\check_release_candidate.py
.\.venv\Scripts\python.exe scripts\check_release_repository.py
git status --short --ignored
```

Pre-commit results:

- publication scanner: passed with zero violations;
- all 11 deterministic `platform_rc_v1` source checks: passed;
- all 15 notebook hashes matched `notebook_hashes_v1`;
- the repository gate failed only because `HEAD` did not yet resolve and the
  approved public files were still untracked. Its publication, notebook,
  staged-change, and tracked-change checks otherwise passed.

The release-candidate script's host capability observations showed Docker as
unavailable because the user-local Docker CLI is not on this PowerShell
session's `PATH`, and the host environment intentionally lacks the optional
model stack. The concrete Docker/model/database evidence below used the
discovered CLI directly and is the authoritative infrastructure result.

### CPU model image

The Phase 11 model image occupied `3,137,724,031` bytes. The rebuilt Phase 12
image occupies `585,249,621` bytes, an approximately 81.3% reduction. The first
new build took 181.7 seconds; an unchanged cached rebuild took 2.5 seconds.

Disposable in-image probes reported:

```text
TORCH_VERSION=2.9.1+cpu
CUDA_AVAILABLE=false
CUDA_PACKAGE_COUNT=0
FLAGEMBEDDING_IMPORT=true
No broken requirements found.
```

This validates CPU packaging and importability. It is not a latency,
throughput, accuracy, or resource-capacity benchmark.

### Independent clean Compose acceptance

A new Compose project named `financial-rag-p12-clean` was created with new
PostgreSQL and model-cache volumes. It did not reuse the earlier project's
database. Host-only port overrides avoided conflicts:

- PostgreSQL: `127.0.0.1:55433`;
- FastAPI: `127.0.0.1:18000`;
- Streamlit: `127.0.0.1:18501`.

`docker compose up --build --wait` passed in 141.2 seconds. PostgreSQL, FastAPI,
and Streamlit were healthy and the one-shot migration service exited `0`.

The acceptance command was:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_acceptance.py --api-url http://127.0.0.1:18000
```

It passed in 168.7 seconds with minimized evidence:

```json
{
  "citation_count": 1,
  "corpus_revision_id": "corpus_a656dfe7029f7d7cc25cdbf4cdb61485",
  "dense_chunk_count": 1,
  "evaluation_completed_modes": [
    "dense",
    "hybrid",
    "hybrid_reranked"
  ],
  "hybrid_chunk_count": 1,
  "index_revision_id": "index_998c801a22508380a26b93feec8c308f",
  "reranked_chunk_count": 1,
  "schema_version": "local_acceptance_result_v1",
  "status": "passed"
}
```

The pass covers the cleared synthetic fixture through ingestion, chunking,
BGE-M3 embedding, PostgreSQL/pgvector persistence, activation, all three
retrieval modes, reranking, one live grounded OpenAI answer with a citation,
and paired retrieval evaluation. The live OpenAI call was made only by this
explicit manual acceptance runner. Automated tests used fakes and made no live
OpenAI call.

The index revision differs from the earlier Phase 11 run because the embedding
runtime dependency changed to the explicit CPU build. No claim of byte-identical
vectors across different dependency builds is made.

The opt-in PostgreSQL integration test was also run inside a clean Linux
container against this database and passed: `1 passed in 0.46s`. The host
Windows test runner remains skipped by default.

### Dependency vulnerability audit

The host audit could not create its isolated environment because of the
bundled Windows Python/`ensurepip` failure. The same strict audit was therefore
run in a disposable `python:3.12-slim-bookworm` container with the repository
mounted read-only:

```powershell
docker run --rm --mount "type=bind,source=$repo,target=/workspace,readonly" `
  --workdir /workspace python:3.12-slim-bookworm sh -c `
  "python -m pip install --disable-pip-version-check -q 'pip-audit>=2.9,<3' && python -m pip_audit --strict ."
```

Result: `No known vulnerabilities found` in 34.1 seconds. This is a
point-in-time dependency-database result, not a permanent security guarantee.

## Public baseline boundary

Before staging, `git status --short --ignored` confirmed that the ignored local
`.env`, virtual environment, caches, database/model artifacts, all source PDFs,
parsed and cleaned text, chunks, embeddings, indexes, contexts/evaluation
outputs, all 15 thesis notebooks, and notebook figures remained excluded.

The only operation involving notebook contents was the approved read-only
SHA-256 comparison against `configs/release/notebook_hashes_v1.sha256`. No
notebook was edited, moved, executed, or formatted. The local `docs.zip` was
neither deleted nor staged; the new archive rule excludes it.

This report is included in the first local baseline commit. Its commit hash is
not embedded here because that would make the commit self-referential. The
post-commit repository gate and exact commit identifier are recorded in the
handoff and Git history.

## Remaining work

- Run every GitHub Actions job on the exact public commit.
- Review the staged/public diff, attribution, screenshots, and draft release
  notes before any public push or tag.
- Decide the remote repository and default-branch policy; no remote is
  configured in this phase.
- Keep authentication, public deployment, multi-user isolation, scaling,
  managed storage, monitoring/SLOs, and a full permitted benchmark run as
  future work.

No public release is approved by this report alone.
