# Phase 9 report - local document and corpus lifecycle

Date: 2026-08-12

## Outcome and scope

Phase 9 was implemented in the agreed sequence:

1. **9A - corpus/index build pipeline:** durable job contracts/store, bounded
   local folder/upload orchestration, ingestion, Markdown-aware chunking,
   embeddings, immutable corpus/index revision persistence, compatibility-safe
   activation, CLI, migration, and synthetic tests;
2. **9B - API and Streamlit lifecycle:** bounded multipart upload, job/revision
   list/read endpoints, explicit index activation, typed demo client, and a
   recruiter-facing Documents tab.

This completes the local path from document input to a queryable revision. It
does not add OCR, a distributed worker, resumability, public deployment,
authentication, malware scanning, multi-user isolation, or managed storage.

No source PDF, parsed/full text artifact, chunk export, embedding/index file,
generated context, model weight, database file/dump, `.env`, FinanceBench row,
or real evaluation result was added.

## Files changed

Added domain and indexing services:

- `src/financial_rag/domain/indexing.py`
- `src/financial_rag/indexing/__init__.py`
- `src/financial_rag/indexing/protocols.py`
- `src/financial_rag/indexing/service.py`
- `src/financial_rag/indexing/staging.py`

Added persistence/runtime support:

- `src/financial_rag/storage/job_store.py`
- `src/financial_rag/runtime/activation.py`
- `migrations/versions/20260812_0002_add_corpus_build_jobs.py`

Updated existing integration surfaces:

- `src/financial_rag/core/errors.py`
- `src/financial_rag/core/__init__.py`
- `src/financial_rag/domain/__init__.py`
- `src/financial_rag/retrieval/dense.py`
- `src/financial_rag/storage/models.py`
- `src/financial_rag/storage/revision_store.py`
- `src/financial_rag/runtime/settings.py`
- `src/financial_rag/runtime/bootstrap.py`
- `src/financial_rag/api/protocols.py`
- `src/financial_rag/api/container.py`
- `src/financial_rag/api/dependencies.py`
- `src/financial_rag/api/schemas.py`
- `src/financial_rag/api/routes.py`
- `src/financial_rag/api/errors.py`
- `src/financial_rag/demo/client.py`
- `src/financial_rag/cli.py`
- `apps/streamlit_app.py`

Added tests:

- `tests/unit/indexing/__init__.py`
- `tests/unit/indexing/test_domain_and_staging.py`
- `tests/unit/indexing/test_service.py`
- `tests/unit/storage/test_job_store.py`
- `tests/unit/runtime/test_activation.py`
- `tests/api/test_corpus_lifecycle.py`

Updated storage/runtime/API/demo tests for the new migration, table, readiness,
revision lists, client methods, CLI, and OpenAPI surface.

Updated configuration, packaging, composition, and documentation:

- `pyproject.toml`
- `.env.example`
- `compose.yaml`
- `README.md`
- `apps/README.md`
- `docs/api-design.md`
- `docs/architecture.md`
- `docs/container-runtime.md`
- `docs/local-runtime.md`
- `docs/storage-design.md`
- `docs/streamlit-demo.md`
- `docs/corpus-lifecycle.md`
- `docs/phase-9-report.md`

## 9A technical decisions

### Job and input boundary

`CorpusBuildJob` has an opaque `job_<uuid hex>` identifier and the states
`pending`, `running`, `completed`, and `failed`. Its contract enforces coherent
timestamps, revision IDs, and safe error codes.

The local upload policy accepts `.pdf`, `.md`, and `.txt` only, with at most 10
files, 20 MiB per file, and 50 MiB total. Filenames cannot contain paths or
control characters and must be unique case-insensitively. The API reads each
multipart file in 64 KiB chunks and stops at the configured bounds.

The staging adapter writes only below an explicit ignored directory. It uses
server-generated names (`01.pdf`, `02.md`, and so on), while portable original
filenames remain source metadata. Cleanup refuses any path outside the exact
job directory and runs after both success and failure.

The CLI `index-folder` applies the same extensions, counts, and byte bounds
before reading direct child files and then routes them through the same staging
and build service.

### Build orchestration and reproducibility

The service uses the existing loaders, chunker, identifiers, `ChunkRecord`
conversion, BGE-M3 embedding port, normalization, fingerprints, and revision
store. It does not change the thesis-derived 1,500/200 chunking defaults or the
`platform_v1` retrieval configuration.

One successful job:

1. transitions to `running`;
2. ingests the stable staged folder order;
3. chunks with full metadata lineage;
4. embeds and validates the 1,024-dimensional L2-normalized matrix;
5. creates the existing `platform_v1` manifest/fingerprints;
6. persists idempotent immutable corpus and index revisions;
7. reloads the persisted index through existing validation;
8. activates the FAISS/BM25/optional-reranker service bundle;
9. records both revision IDs and transitions to `completed`.

Expected failures become a safe category such as `ingestion_failed`,
`chunking_failed`, `embedding_failed`, or `persistence_failed`; raw exception
messages are not stored in job state. Only one pending/running job is accepted
by the local service instance.

`DenseIndex.from_embeddings()` is the only new retrieval primitive. It creates
the existing exact `IndexFlatIP` from already validated persisted vectors; it
does not introduce approximate or SQL-native retrieval.

### Persistence and restart behavior

Migration `20260812_0002` adds only `corpus_build_jobs`. The table contains
status, label, file count, safe error code, revision references, and timestamps.
It deliberately has no filename, local path, raw input, parsed text, chunk,
vector, prompt, or provider-response column.

Transitions lock the job row and require the expected prior status. Local
runtime startup marks leftover `pending`/`running` jobs failed with
`runtime_interrupted`. This is durable failure visibility, not job resumption.

`PostgresRevisionStore` now provides bounded newest-first corpus/index metadata
lists without loading chunks or vectors.

### Index activation

Activation reloads and verifies the selected persisted index, corpus status,
embedding model/dimension/normalization, retrieval-configuration fingerprint,
and chunk mapping. Only after constructing the complete replacement retrieval,
generation, and evaluation services does it update the local single-user
container. The active selection is process-local and is not silently restored
after restart.

## 9B API and Streamlit decisions

New routes:

```text
POST /api/v1/corpus-jobs
GET  /api/v1/corpus-jobs
GET  /api/v1/corpus-jobs/{job_id}
GET  /api/v1/corpora
GET  /api/v1/indexes
POST /api/v1/indexes/{index_revision_id}/activate
```

The POST returns HTTP 202 after staging and durable pending-job creation. A
Starlette background task runs the bounded in-process build. There is no worker,
queue, cancellation, retry, resumable state, or percent-complete claim.

The job and list responses omit uploaded filenames/content, chunks, and vectors.
Readiness reports indexing separately. Missing jobs map to 404, invalid job
transitions to 409, and upload policy rejection to a safe 400 envelope.

The Streamlit `Documents` tab:

- uploads the supported bounded file types through FastAPI only;
- accepts an optional corpus label;
- displays privacy-minimized job status and safe error codes;
- refreshes jobs and revision lists only on user action;
- activates a ready index for later Ask/Compare/Evaluate requests.

The UI receives no database/model/OpenAI credentials and imports no backend
adapter. It does not claim streaming progress.

## Dependencies and migration checks

`python-multipart>=0.0.20,<1` is the only new runtime dependency. It is required
by FastAPI's multipart boundary and was already present transitively in the
managed environment.

The normal editable command was represented by the equivalent managed-Python
installer because this workspace has no Windows `py` launcher and its `.venv`
has no embedded pip module:

```powershell
& "<managed-python>\python.exe" -m pip --python .\.venv install -e ".[api,evaluation,demo,dev]"
```

Actual result: success; the editable project was rebuilt and all dependencies
were satisfied.

Migration commands:

```powershell
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic `
  -x database_url=postgresql+asyncpg://synthetic:synthetic@localhost/synthetic `
  upgrade head --sql
```

Actual results:

- exactly one head: `20260812_0002`;
- offline PostgreSQL SQL rendered successfully from base through both revisions;
- the output contained the new table/check constraints/foreign keys/index and
  updated `alembic_version` to `20260812_0002`;
- no database connection was opened.

## Verification actually performed

Final source commands:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
.\.venv\Scripts\python.exe scripts/check_publication.py
```

Final results after this report was added:

- Ruff lint: all checks passed.
- Ruff format: all files already formatted.
- Strict mypy: no issues in 139 source files.
- Pytest: 216 passed, 1 skipped.
- Branch-enabled package coverage: 87%.
- The one skip remains the opt-in PostgreSQL integration test because
  `TEST_DATABASE_URL` is not configured.
- Publication gate: passed for 197 candidate files.
- No automated test made a live model, OpenAI, HTTP network, or database call.

Additional smoke checks:

- import/application construction succeeded;
- OpenAPI exposed 12 paths, including all six new lifecycle routes;
- CLI help exposed `evaluate-retrieval` and `index-folder`;
- Streamlit `AppTest` reported zero exceptions, five tabs (`Documents`, `Ask`,
  `Compare retrieval`, `Evaluate`, `Current scope`), and two upload controls.

## Infrastructure checks not claimed

Docker is still unavailable on this machine, so Compose config, image build,
container migration, and container end-to-end smoke were not rerun locally.
The Phase 8 CI jobs contain those checks but no remote GitHub Actions run was
performed here.

No PostgreSQL URL/server was configured, so the new migration and full
ingestion-to-real-pgvector integration path were not executed against live
infrastructure. Offline migration SQL, SQLite transactional store tests, and
synthetic end-to-end service tests passed; they are not presented as a live
PostgreSQL smoke.

The optional `models` extra was not installed or invoked. Synthetic fake
embeddings covered orchestration, and no BGE weights were downloaded. No live
OpenAI call was made.

## Publication and immutable artifacts

`git check-ignore -v` confirms `.env`, upload staging, FinanceBench data, PDFs,
indexes, evaluation runs, model cache, and notebooks remain ignored. All 15
notebooks were enumerated and hashed read-only; none was opened for writing,
executed, formatted, moved, deleted, staged, or committed.

`git status --short --ignored` continues to show the public project tree as
untracked and restricted local artifacts/caches as ignored. The Git metadata
still has no resolvable `HEAD`; Phase 9 did not alter repository history.

No staging, commit, branch, push, release, database mutation, or deployment was
performed.

## Exact local commands

Source environment and checks:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[api,models,evaluation,demo,dev]"
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Database and local services:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\uvicorn.exe financial_rag.runtime.app:create_local_app `
  --factory --host 127.0.0.1 --port 8000
.\.venv\Scripts\streamlit.exe run apps\streamlit_app.py `
  --server.address 127.0.0.1 --server.port 8501
```

Set `DATABASE_ENABLED=true` and a real local `DATABASE_URL` only inside ignored
`.env`. `OPENAI_API_KEY` remains optional and is required only for grounded
generation.

## Next boundary

Phase 10 should be a release-candidate validation phase rather than another
large feature phase: run the Compose PostgreSQL/model path with a separately
cleared synthetic document, exercise upload-to-query-to-evaluation end to end,
capture sanitized evidence, address dependency audit results, and freeze a
reviewed release checklist. Public deployment remains out of scope until
authentication, quotas, secret management, storage/retention, and ingress
controls exist.

Phase 9 stops here for review.
