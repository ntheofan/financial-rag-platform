# Phase 4 report — FastAPI over tested services

Date: 2026-08-02

## Outcome and scope boundary

Phase 4 adds a typed, versioned FastAPI adapter over the existing Phase 2
retrieval service and Phase 3 revision store. It provides an application factory,
explicit dependency injection, health/readiness, all three retrieval modes,
read-only corpus/index revision metadata, OpenAPI, request correlation,
structured request logging, and consistent error mapping.

The original audit roadmap grouped grounded generation with FastAPI. The
approved instruction for this phase specifically requested FastAPI over already
tested services. Generation, prompt building, OpenAI/LangChain OpenAI, answer
citations, document upload, background jobs, evaluation, Docker, Streamlit,
authentication, and public deployment were therefore not implemented.

## Files changed

Updated:

- `.env.example`
- `README.md`
- `pyproject.toml`
- `src/financial_rag/core/__init__.py`
- `src/financial_rag/storage/revision_store.py`
- `src/financial_rag/api/__init__.py`

Added API implementation:

- `src/financial_rag/api/app.py`
- `src/financial_rag/api/container.py`
- `src/financial_rag/api/dependencies.py`
- `src/financial_rag/api/errors.py`
- `src/financial_rag/api/middleware.py`
- `src/financial_rag/api/protocols.py`
- `src/financial_rag/api/routes.py`
- `src/financial_rag/api/schemas.py`
- `src/financial_rag/api/settings.py`

Added tests and documentation:

- `tests/api/__init__.py`
- `tests/api/client.py`
- `tests/api/helpers.py`
- `tests/api/test_health_and_openapi.py`
- `tests/api/test_retrieval.py`
- `tests/api/test_revisions_and_errors.py`
- `docs/api-design.md`
- `docs/phase-4-report.md`

The existing Phase 3 storage tests were extended to cover metadata-only corpus
and index readers. No migration or database schema change was required.

## Technical decisions

### Thin adapter and dependency injection

`create_app()` accepts an immutable `ApiContainer` containing structural ports,
not concrete model/database constructors. Importing the API and constructing its
default application does not load a model, read retrieval artifacts, open a
database connection, or make a network call.

The default empty container exposes liveness and OpenAPI safely, reports
readiness as HTTP 503, and rejects service-dependent routes with HTTP 503. This
is deliberate: Phase 4 does not silently select a corpus, model, GPU, index, or
database. A later composition/deployment phase can inject concrete tested
instances without changing HTTP contracts.

The synchronous Phase 2 retrieval call runs through Starlette's thread pool so
FAISS/model work does not block the ASGI event loop. Revision metadata methods
are asynchronous and do not load full chunk text or embedding vectors.

### HTTP contract

Implemented routes:

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/retrieval/query`
- `GET /api/v1/corpora/{corpus_revision_id}`
- `GET /api/v1/indexes/{index_revision_id}`

The query endpoint accepts `dense`, `hybrid`, and `hybrid_reranked` and returns
the existing `RetrievalResult` without score hiding or context truncation. It
does not claim to return an answer. Corpus/index routes return only revision
metadata, counts, and fingerprints.

OpenAPI documents request examples, response schemas, path-identifier patterns,
and shared 400/404/409/422/500/503 error envelopes. Documentation routes can be
disabled with `API_DOCS_ENABLED=false`.

### Errors, privacy, and logging

Validation details omit submitted values. Provider and unexpected exception
details receive non-sensitive 503/500 responses. Every normal and error response
has an `X-Request-ID`; supplied IDs are length/character validated.

Structured logs record only request ID, method, declared route template, status,
and duration. They do not log raw unmatched paths, query strings, bodies,
retrieved chunks, headers, credentials, or database URLs.

No authentication, authorization, rate limiting, CORS, trusted-proxy policy, or
TLS is claimed. The API remains local, single-user, and unsuitable for public
binding.

## Dependencies

FastAPI moved into runtime dependencies because the API is now implemented.
Uvicorn remains in the optional `api` extra. `httpx` is explicit in test/dev
groups for modern in-process ASGI tests. `python-multipart` was removed because
Phase 4 has no upload endpoint.

Actual installed versions in the verification environment included FastAPI
0.141.1, Uvicorn 0.52.1, Starlette 1.3.1, and HTTPX 0.28.1. Tests use
`httpx.AsyncClient` with `ASGITransport`; no live HTTP or external network call
is made by pytest.

## Verification actually performed

### Installation

Attempted portable command:

```powershell
py -3.12 -m pip install -e ".[api,dev]"
```

Actual result: exit code 1, `No installed Python found!`.

The managed Python 3.12 runtime was used to install the same editable extras into
the existing `.venv`. Actual result: success, including FastAPI and Uvicorn.

### Quality and automated tests

Commands:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Final results:

- Ruff lint: all checks passed.
- Ruff format: 105 files already formatted.
- Mypy strict: no issues in 86 source files.
- Pytest: 113 passed, 1 skipped.
- Total branch-enabled coverage: 91%.
- API-only suite: 18 passed with synthetic injected services.
- The one skipped test remains the opt-in live PostgreSQL infrastructure check;
  `TEST_DATABASE_URL` was not configured.

API tests exercised all retrieval modes, hybrid defaulting, full metadata/score
responses, request validation, missing services, provider failures, unexpected
errors, revision metadata, identifier validation, liveness/readiness, request
IDs, OpenAPI, and disabled documentation. Deterministic fake embedding/reranker
providers and synthetic content were used; no real model or OpenAI call ran.

### Import/OpenAPI and Uvicorn smoke checks

The factory import/OpenAPI check reported:

- Python 3.12.13;
- application `financial-rag-platform`, version `0.1.0`;
- exactly five documented paths;
- empty default `ApiContainer` without infrastructure access.

Uvicorn 0.52.1 was started locally and hidden on `127.0.0.1:8765` using the
factory form. Actual responses:

- `/health/live`: HTTP 200 with status `ok`;
- `/health/ready`: HTTP 503, as expected for the empty container;
- `/openapi.json`: HTTP 200 with five paths.

The first PowerShell readiness probe attempted the newer
`Invoke-WebRequest -SkipHttpErrorCheck` option, which was unavailable in the
installed PowerShell and emitted a parameter error. It was rerun with compatible
try/catch status handling and produced the expected 503. The exact spawned
Uvicorn process was then stopped and verified absent.

Local commands for a developer with the Python launcher are:

```powershell
py -3.12 -m pip install -e ".[api,dev]"
.\.venv\Scripts\uvicorn.exe financial_rag.api.app:create_app --factory --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/openapi.json | Out-Null
```

The empty factory intentionally cannot serve a real retrieval request. Concrete
retrieval/storage services must be composed and injected explicitly.

## Publication and immutable artifacts

Final publication checks cover `git status --short --ignored`, the complete
non-ignored untracked file list, ignore rules for `.env`, data, indexes, database
runtime paths, credential/local-path scanning, and SHA-256 hashes for all 15
notebooks.

No source PDF, parsed/cleaned text, chunk corpus, real embedding/index, generated
context, database, dump, model cache, `.env`, secret, or new benchmark artifact
was created. The 15 notebook hashes remain equal to the Phase 3/audit baseline.
No notebook was moved, executed, formatted, or edited.

Git still reports `No commits yet on master`. No staging, commit, branch, push,
delete, or move operation was performed.

## Known limitations and next boundary

- The default factory is intentionally unconfigured; concrete service bootstrap
  and lifecycle disposal still need an explicitly approved composition phase.
- Readiness reports injected capability, not a live database/model/GPU probe.
- There is no upload/document-management endpoint or job lifecycle.
- There is no answer generation or validated answer-citation contract.
- There is no live PostgreSQL/API integration run with real artifacts.
- Public deployment security and operational controls are absent.

A next phase may implement grounded generation/citations or an explicit local
composition/bootstrap layer, but neither is included without separate approval.

Phase 4 stops here for review.
