# Phase 6 report — recruiter-friendly Streamlit client

Date: 2026-08-02

## Outcome and scope boundary

Phase 6 adds a local Streamlit interface over the existing Phase 4/5 FastAPI
contracts. It provides grounded question answering, citation inspection,
retrieved-chunk score traces, readiness feedback, and a side-by-side comparison
of `dense`, `hybrid`, and `hybrid_reranked`.

The original audit described the Streamlit client as Phase 5. The implemented
sequence used Phase 5 for the previously missing composition and grounded
generation work, so the UI is recorded as Phase 6.

Document upload and corpus selection were intentionally not implemented or
simulated. The backend still lacks document-management, ingestion-job, and
index-build endpoints. Adding an upload widget that cannot complete a safe
backend lifecycle would create a misleading demo claim. The current UI queries
one explicitly configured, ignored local retrieval artifact directory.

This phase does not add database/model access to Streamlit, OpenAI credentials
to browser state, Docker, authentication, public deployment, evaluation runs,
or new benchmark claims.

## Files changed

Updated:

- `.env.example`
- `README.md`
- `apps/README.md`

Added application and typed demo boundary:

- `apps/streamlit_app.py`
- `src/financial_rag/demo/__init__.py`
- `src/financial_rag/demo/client.py`
- `src/financial_rag/demo/presentation.py`
- `src/financial_rag/demo/settings.py`

Added tests and documentation:

- `tests/unit/demo/__init__.py`
- `tests/unit/demo/test_client.py`
- `tests/unit/demo/test_presentation_and_settings.py`
- `docs/streamlit-demo.md`
- `docs/phase-6-report.md`

No FastAPI route, retrieval algorithm, generation prompt, database model,
migration, ingestion behavior, or notebook was changed.

## Technical decisions

### HTTP-only UI boundary

`FinancialRagApiClient` consumes only:

- `GET /health/ready`;
- `POST /api/v1/query`;
- `POST /api/v1/retrieval/query`.

It validates successful and error responses against the existing Pydantic
contracts. It has no storage, FAISS, embedding, reranker, or OpenAI imports. The
only demo settings are the FastAPI base URL and request timeout; tests assert
that no provider-key setting exists in the UI configuration.

Malformed responses, unreachable APIs, and backend error envelopes are mapped
to short display-safe errors. Connection exception details are not shown. A
three-mode comparison retains successful results if another mode fails instead
of collapsing the complete comparison.

### Recruiter-facing views

The `Ask` view contains a question form and retrieval-mode selector. It renders:

- grounded answer or explicit abstention;
- model identifier and token usage when returned;
- expandable request-local citation contexts;
- source file, page, section, chunk ID, and retrieval rank;
- the complete returned retrieval trace;
- dense, BM25, RRF, and reranker scores only when applicable.

The `Compare retrieval` view sends the same stripped query to the three modes in
fixed order. It displays the first five chunks per mode and Jaccard overlap of
returned chunk-ID sets. Overlap is labeled as a display diagnostic, not an
answer-quality or benchmark metric.

The sidebar readiness action is user-triggered; importing/rendering the initial
module does not poll the backend. The page states that it is a local development
demo and not financial or investment advice.

### Data and secret handling

`OPENAI_API_KEY` remains a backend-only setting. The UI may hold an answer and
its contexts temporarily in Streamlit session state, but it does not persist
them to disk or emit them to logs. Real-corpus screenshots and browser exports
remain prohibited public artifacts unless separately cleared.

`FINANCIAL_RAG_API_URL` rejects embedded credentials, query strings, fragments,
and non-HTTP schemes. Both documented processes bind to loopback.

## Dependency installation

No new dependency declaration was required: the existing `demo` optional group
already contained `httpx` and `streamlit`.

The existing managed environment did not have Streamlit. Installation was run
with the bundled Python pip targeting the existing `.venv`:

```powershell
& "<managed-python>\python.exe" -m pip --python .\.venv install -e ".[demo,dev]"
```

Actual result: success. Streamlit 1.60.0 and its dependencies were installed;
the project remained an editable install. A normal local environment should
use:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[api,models,demo,dev]"
```

## Tests and verification actually performed

The first targeted run used:

```powershell
.\.venv\Scripts\ruff.exe check src apps tests/unit/demo
.\.venv\Scripts\ruff.exe format --check src apps tests/unit/demo
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe tests/unit/demo tests/api -q
```

Ruff lint passed, mypy passed, and 34 tests passed. Ruff format identified one
test assertion that needed mechanical wrapping; it was corrected before the
full verification.

Final commands:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Final results:

- Ruff lint: all checks passed.
- Ruff format: 137 files already formatted.
- Mypy strict: no issues in 112 source files.
- Pytest: 158 passed, 1 skipped.
- Branch-enabled total coverage: 90%.
- The one skip remains the opt-in PostgreSQL integration test because
  `TEST_DATABASE_URL` is not configured.
- Demo client coverage is 88%; pure presentation-helper coverage is 93%.
- No automated test made a live HTTP, OpenAI, model-download, or database call.

Offline client tests use `httpx.MockTransport` and synthetic domain responses.
They cover readiness HTTP 503, full grounded-answer parsing, identical paired
queries, fixed mode order, partial failures, safe connection errors, malformed
responses, URL restrictions, score presentation, and overlap calculation.

Streamlit's `AppTest` loaded `apps/streamlit_app.py` with no backend configured.
Actual result:

```text
exceptions: 0
title: Financial Document Intelligence
tabs: Ask, Compare retrieval, Current scope
```

A real hidden Streamlit process was then started on `127.0.0.1:8511`. Its
`/_stcore/health` endpoint returned HTTP 200 with body `ok`. The exact process
was stopped and a final port check confirmed no listener remained.

## Exact local run commands

After configuring the ignored `.env`, start the backend:

```powershell
.\.venv\Scripts\uvicorn.exe financial_rag.runtime.app:create_local_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, start Streamlit:

```powershell
.\.venv\Scripts\streamlit.exe run apps\streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Then open `http://127.0.0.1:8501` and use the explicit sidebar readiness check.
If retrieval is not configured, the UI reports the backend state rather than
claiming that a corpus is available. Grounded answer generation additionally
requires the backend-only OpenAI key.

## Publication and immutable artifacts

No source PDF, parsed/cleaned text, chunk corpus, embedding/index, generated
context capture, database/dump, model cache, `.env`, credential, screenshot, or
benchmark result was created. The 15 thesis notebooks were not opened for
writing, executed, formatted, moved, or deleted.

The final publication check must continue to treat `.env`, local data,
artifacts, caches, and all notebook files as ignored. No staging, commit, branch,
push, move, or deletion is part of this phase.

## Known limitations and next boundary

- There is no document upload/list/select or ingestion/index job API.
- One configured local corpus is used at a time.
- The UI is synchronous and intended for one local user.
- Streamlit session state is transient, not a durable query history.
- Comparison overlap is diagnostic only; evaluation metrics are not implemented.
- There is no authentication, TLS, rate limiting, public hosting, or deployment
  hardening.
- Docker/Compose and a FinanceBench-like evaluation subsystem remain future work.

Phase 6 stops here for review.
