# Phase 5 report — local composition and grounded generation

Date: 2026-08-02

## Outcome and scope

Phase 5 was implemented in the two approved, sequential checkpoints:

1. local composition/bootstrap with versioned configuration, ASGI lifecycle,
   explicit retrieval artifact loading, and an opt-in PostgreSQL smoke probe;
2. grounded generation with bounded top-five context assembly, an official
   OpenAI SDK adapter, structured answers, citation lineage, and HTTP exposure.

The result is still a local, single-user development demo. This phase does not
add uploads, ingestion endpoints, index creation jobs, evaluation runs, Docker,
Streamlit, authentication, public deployment, managed storage, scaling, or a
claim-level factual verifier.

## Files changed

Updated configuration and project documentation:

- `.env.example`
- `README.md`
- `pyproject.toml`
- `configs/README.md`
- `docs/api-design.md`

Added versioned runtime configuration and design documentation:

- `configs/runtime/local_v1.json`
- `docs/local-runtime.md`
- `docs/grounded-generation.md`
- `docs/phase-5-report.md`

Updated existing package boundaries:

- `src/financial_rag/api/app.py`
- `src/financial_rag/api/container.py`
- `src/financial_rag/api/dependencies.py`
- `src/financial_rag/api/errors.py`
- `src/financial_rag/api/protocols.py`
- `src/financial_rag/api/routes.py`
- `src/financial_rag/api/schemas.py`
- `src/financial_rag/core/__init__.py`
- `src/financial_rag/core/errors.py`
- `src/financial_rag/generation/__init__.py`

Added Phase 5 implementation:

- `src/financial_rag/domain/generation.py`
- `src/financial_rag/generation/context.py`
- `src/financial_rag/generation/openai_adapter.py`
- `src/financial_rag/generation/prompting.py`
- `src/financial_rag/generation/protocols.py`
- `src/financial_rag/generation/service.py`
- `src/financial_rag/runtime/__init__.py`
- `src/financial_rag/runtime/app.py`
- `src/financial_rag/runtime/bootstrap.py`
- `src/financial_rag/runtime/settings.py`

Added or updated offline tests:

- `tests/api/test_generation.py`
- `tests/api/test_health_and_openapi.py`
- `tests/unit/generation/__init__.py`
- `tests/unit/generation/helpers.py`
- `tests/unit/generation/test_context_and_prompting.py`
- `tests/unit/generation/test_openai_adapter.py`
- `tests/unit/generation/test_service.py`
- `tests/unit/runtime/__init__.py`
- `tests/unit/runtime/test_bootstrap.py`
- `tests/unit/runtime/test_settings.py`

## Checkpoint 1 — local composition/bootstrap

`LocalRuntimeSettings` keeps secrets, machine-specific paths, and infrastructure
switches in `.env`. `LocalRuntimeConfig` validates the checked-in `local_v1`
contract, which references `platform_v1`, preserves the Phase 1 chunking
configuration, and records local model/context settings.

`LocalRuntimeBuilder` now composes:

- a `RetrievalService` only from an explicitly configured, compatibility-checked
  local artifact directory;
- lazy BGE-M3 embedding/reranking adapters, without loading model weights during
  startup;
- a SQLAlchemy async engine and `PostgresRevisionStore` only when the database
  switch is enabled;
- an optional startup probe for `SELECT 1`, the PostgreSQL `vector` extension,
  and Alembic head `20260801_0001`;
- grounded generation only when both retrieval and an OpenAI key are configured.

`create_local_app()` owns these resources through FastAPI lifespan and disposes
the engine at shutdown. No-artifact startup is intentionally safe but reports
retrieval/generation unavailable. An explicit invalid artifact path fails
startup rather than silently selecting another corpus.

Checkpoint verification, after local corrections:

```powershell
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\ruff.exe format --check src tests
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe tests/unit/runtime tests/api -q
```

Actual result: Ruff passed, 93 files were formatted, mypy found no issues in 93
source files, and 28 tests passed.

## Checkpoint 2 — grounded generation and citations

The generation layer is deliberately provider-neutral above its adapter. It
adds:

- deterministic selection of at most the top five retrieval results;
- request-local `C1`–`C5` labels and complete chunk/document lineage;
- a 6,000-token context budget using a documented deterministic whitespace
  estimate, with explicit final-context truncation metadata;
- prompt construction that treats retrieved text as untrusted evidence and
  instructs abstention when evidence is insufficient;
- Pydantic structured provider output and provider usage metadata;
- strict rejection of missing, duplicate, unknown, or abstention-incompatible
  citations;
- a no-context abstention path that does not call the provider;
- `POST /api/v1/query`, returning answer, citations, exact contexts, and the
  original transparent retrieval scores.

Citation validation proves that returned citation IDs refer to contexts actually
supplied to the model. It does not prove semantic entailment of every generated
claim, so no stronger grounding or answer-correctness claim is made.

The default adapter uses the official OpenAI Python SDK Responses API structured
parser, `store=false`, explicit timeout/retry/output bounds, and a configurable
model (default `gpt-4o-mini`). It is lazy and receives the API key as
`SecretStr`. Automated tests inject fake clients and never perform live calls.

Targeted checkpoint result: Ruff and formatting passed after one formatting
correction, strict mypy passed, and 43 generation/runtime/API tests passed.

## Dependency installation

Added runtime dependency:

```text
openai>=2,<3
```

The requested portable command was attempted:

```powershell
py -3.12 -m pip install -e ".[dev]"
```

Actual result: exit code 1, `No installed Python found!`, because this managed
environment has no Windows `py` launcher.

An attempt to bootstrap pip through the existing `.venv` Python also failed in
the managed runtime with `OPENSSL_Applink`. Installation was then performed into
the same `.venv` using the bundled Python's pip target support:

```powershell
& "<managed-python>\python.exe" -m pip --python .\.venv install -e ".[dev]"
```

Actual result: success. The resulting environment uses Python 3.12.13, OpenAI
2.52.0, FastAPI 0.141.1, and Pydantic 2.13.4. Inspection of the installed SDK
source confirmed that `responses.parse` accepts `text_format`, `instructions`,
`input`, `max_output_tokens`, and `store`, matching the implemented adapter.

For a normal local Python installation, use:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[api,models,dev]"
```

Then create local configuration and start the composed application:

```powershell
Copy-Item .env.example .env
# Edit only the ignored .env: set RETRIEVAL_ARTIFACT_DIRECTORY and, optionally,
# OPENAI_API_KEY. Enable DATABASE_ENABLED only when local PostgreSQL is ready.
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe financial_rag.runtime.app:create_local_app --factory --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Run Alembic only when `DATABASE_URL` points to the intended local PostgreSQL
database. Set `DATABASE_SMOKE_ON_STARTUP=true` to opt into the startup probe.
For an explicit integration check, set a separate local `TEST_DATABASE_URL` and
run:

```powershell
.\.venv\Scripts\pytest.exe tests/integration/storage/test_migrated_database.py -q -rs
```

## Final verification actually performed

Commands:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Final results:

- Ruff lint: all checks passed.
- Ruff format: 127 files already formatted.
- Mypy strict: no issues in 105 source files.
- Pytest: 144 passed, 1 skipped.
- Branch-enabled total coverage: 90%.
- The skipped test is the opt-in migrated PostgreSQL integration test because
  `TEST_DATABASE_URL` is not configured.
- No automated test made an OpenAI, model-download, or other network call.

The local import/OpenAPI smoke command reported package version `0.1.0` and six
paths:

```text
/health/live
/health/ready
/api/v1/query
/api/v1/retrieval/query
/api/v1/corpora/{corpus_revision_id}
/api/v1/indexes/{index_revision_id}
```

The PostgreSQL smoke behavior is covered with fake async engine/connection
objects. A live PostgreSQL/pgvector/Alembic smoke was not run because no approved
`TEST_DATABASE_URL` was configured.

## Publication and immutable artifacts

`git check-ignore -v` confirmed ignore coverage for `.env`, FinanceBench data,
source PDFs, embeddings/FAISS artifacts, and thesis notebooks. A secret-pattern
scan outside `.git`, `.venv`, notebooks, and data returned no matches. The
current SHA-256 command enumerated all 15 notebook files; no Phase 5 command
opened them for writing, executed them, formatted them, moved them, or deleted
them.

`git status --short --ignored` continues to show local caches, `.venv`, all
restricted data artifacts, and all 15 notebooks as ignored. It also reports the
project files as untracked. `git rev-parse --verify HEAD` returned
`fatal: Needed a single revision`, so this workspace's observable Git metadata
does not contain the baseline commit mentioned in the instruction. No staging,
commit, branch, push, move, or deletion was performed in Phase 5.

No source PDF, parsed/cleaned corpus, chunks, embedding/index, generated context,
answer capture, database/dump, model cache, `.env`, key, or new benchmark result
was added.

## Known limitations and next boundary

- The local runtime requires a separately created, ignored Phase 2 artifact
  directory; it does not yet build an index from an upload.
- BGE-M3 model weights remain an optional local dependency and were not loaded
  during verification.
- The context budget uses a deterministic estimate, not OpenAI's billing
  tokenizer.
- Citation membership is enforced, but claim-level entailment is not.
- Readiness reports configured capability; continuous dependency health and
  operational monitoring are absent.
- Live OpenAI and PostgreSQL requests require explicit local configuration and
  were not exercised.
- Docker, Streamlit, evaluation workflows, authentication, public deployment,
  scaling, and managed persistence remain future work.

Phase 5 stops here for review.
