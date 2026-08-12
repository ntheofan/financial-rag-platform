# Phase 7 report — evaluation core, API, and Streamlit view

Date: 2026-08-12

## Outcome and scope

Phase 7 was implemented in the two approved sequential checkpoints:

1. **7A — offline evaluation core:** strict benchmark import, paired retrieval
   execution, canonical Hit@K/MRR, optional deterministic answer metrics,
   provenance manifests, privacy-minimized JSON reports, and a CLI;
2. **7B — evaluation presentation:** local runtime composition, a bounded
   synchronous FastAPI endpoint, typed demo-client support, and a Streamlit
   evaluation view.

The corrected protocol is named `platform_eval_v1`. Historical thesis results
remain `research_legacy_v1`; they were not modified, relabeled, rerun, or used as
new benchmark claims.

Only a two-row synthetic JSONL fixture was added. No FinanceBench row, source
PDF, evidence page, parsed text, chunk content, embedding/index, generated
answer, or real evaluation output was added.

RAGAS/RAGChecker, durable evaluation jobs, PostgreSQL evaluation tables,
background workers, Docker, and public deployment are outside Phase 7A/7B.

## Files changed

Added Phase 7 configuration and domain/core implementation:

- `configs/evaluation/platform_eval_v1.json`
- `src/financial_rag/cli.py`
- `src/financial_rag/domain/evaluation.py`
- `src/financial_rag/evaluation/importers.py`
- `src/financial_rag/evaluation/metrics.py`
- `src/financial_rag/evaluation/reports.py`
- `src/financial_rag/evaluation/runner.py`

Updated package and error exports:

- `src/financial_rag/core/errors.py`
- `src/financial_rag/core/__init__.py`
- `src/financial_rag/evaluation/__init__.py`

Updated Phase 7B API/runtime/demo integration:

- `src/financial_rag/api/container.py`
- `src/financial_rag/api/dependencies.py`
- `src/financial_rag/api/protocols.py`
- `src/financial_rag/api/routes.py`
- `src/financial_rag/api/schemas.py`
- `src/financial_rag/runtime/bootstrap.py`
- `src/financial_rag/demo/client.py`
- `apps/streamlit_app.py`

Added synthetic fixture and tests:

- `tests/fixtures/evaluation/benchmark.jsonl`
- `tests/unit/evaluation/__init__.py`
- `tests/unit/evaluation/test_cli.py`
- `tests/unit/evaluation/test_importers.py`
- `tests/unit/evaluation/test_metrics.py`
- `tests/unit/evaluation/test_runner_and_reports.py`
- `tests/api/test_evaluation.py`

Updated existing tests:

- `tests/api/helpers.py`
- `tests/api/test_health_and_openapi.py`
- `tests/unit/demo/test_client.py`
- `tests/unit/runtime/test_bootstrap.py`

Updated project documentation/configuration:

- `README.md`
- `pyproject.toml`
- `apps/README.md`
- `configs/README.md`
- `scripts/README.md`
- `docs/api-design.md`
- `docs/streamlit-demo.md`
- `docs/evaluation.md`
- `docs/phase-7-report.md`

No database model or Alembic migration changed because Phase 7 reports are not
persisted by the application.

## Checkpoint 7A — offline evaluation core

### Benchmark contract and import

`platform_eval_dataset_v1` requires:

- unique bounded `query_id` values;
- a bounded non-empty query;
- one or more unique, non-blank relevant chunk IDs;
- an optional bounded reference answer.

The importer supports local UTF-8 `.json` and `.jsonl`, up to 5 MiB and 500
items. JSON may be a complete dataset object or an item array. JSONL is one item
per non-empty line. Unsupported, empty, oversized, malformed, non-UTF-8, or
schema-incompatible input fails with `BenchmarkImportError` and no content echo.

Relevance is explicitly chunk-ID membership. This phase does not silently turn
document/page annotations into chunk relevance or use fuzzy text matching.

### Paired execution and metrics

The runner evaluates the identical validated query set across the configured
ordered modes. The checked-in config uses Dense, Hybrid, and Hybrid + Reranker,
with Hit@1/3/5/10.

Implemented retrieval metrics:

- first relevant rank;
- reciprocal rank;
- binary Hit@K;
- per-mode MRR and mean Hit@K.

A successfully executed miss is numeric zero. A retrieval failure is `failed`,
has null metrics, is counted separately, and is excluded from the metric
denominator. This corrects the notebook behavior where some skipped/failed work
could appear as score zero.

Optional answer evaluation provides normalized exact match and token F1. Missing
references, disabled metrics, or unavailable generation are `skipped` with null
metrics. Provider/domain failures are `failed` with null metrics. The report
records abstention but omits generated/reference answer text.

### Provenance, privacy, and CLI

Every report records dataset, evaluation config, retrieval config, and optional
corpus fingerprints, plus run ID/time, explicit denominators, the paired matrix,
retrieved chunk IDs, and safe issue codes. It omits query text, answers, source
filenames, and chunk content.

JSON export requires an explicit `.json` path and does not overwrite by default.
The documented output directory `evaluation-runs/` is already ignored.

CLI entry point:

```powershell
.\.venv\Scripts\python.exe -m financial_rag.cli evaluate-retrieval --help
```

The real help command succeeded and listed explicit benchmark, artifact,
runtime/evaluation config, dataset ID, output, and overwrite options. A full CLI
success path was tested with a real `RetrievalService`, synthetic chunks, an
injected local runtime boundary, and a temporary report; no model/network call
occurred and the runtime was closed.

7A checkpoint commands:

```powershell
.\.venv\Scripts\ruff.exe check src tests/unit/evaluation
.\.venv\Scripts\ruff.exe format --check src tests/unit/evaluation
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe tests/unit/evaluation -q
```

Actual checkpoint result: Ruff and formatting passed, strict mypy passed, and
18 evaluation tests passed. The later CLI success test increased the final
evaluation test count after this checkpoint.

## Checkpoint 7B — FastAPI and Streamlit presentation

### FastAPI/runtime

`EvaluationUseCase` is injected through `ApiContainer`. The local runtime creates
an `EvaluationRunner` only when retrieval is configured, supplies generation
when available, and propagates the index chunk-mapping fingerprint as corpus
provenance.

New endpoint:

```text
POST /api/v1/evaluations/retrieval
```

It accepts one validated dataset/config and returns the complete synchronous
report. The endpoint runs through the thread pool and uses the existing safe
error envelope. `/health/ready` now reports evaluation capability separately.

This is intentionally not presented as a durable evaluation job API. There is
no run persistence, GET-by-ID, cancellation, progress, or multi-user scheduling.
The 500-item bound is suitable only for the local single-user demo.

### Streamlit

The `Evaluate` tab:

- accepts `.json`/`.jsonl` in memory;
- selects Hit@K cutoffs and optional answer metrics;
- calls FastAPI through `FinancialRagApiClient` only;
- renders per-mode MRR/Hit@K and answer aggregates;
- renders per-query retrieval/answer status and null metrics honestly.

It does not persist the uploaded benchmark or report and does not access the
database, retrieval models, index, or OpenAI SDK directly.

7B checkpoint commands:

```powershell
.\.venv\Scripts\ruff.exe check src apps tests
.\.venv\Scripts\ruff.exe format --check src apps tests
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe tests/unit/evaluation tests/unit/demo tests/unit/runtime tests/api -q
```

Actual result: Ruff/format/mypy passed and 71 targeted tests passed.
Streamlit `AppTest` reported zero exceptions and four tabs: `Ask`,
`Compare retrieval`, `Evaluate`, and `Current scope`.

## Dependencies and installation

The evaluation core uses only existing Python/runtime dependencies. Unused
`datasets` and direct `pandas` declarations were removed from the `evaluation`
extra. The empty extra remains a stable future install target for optional
evaluator adapters. Pandas remains an indirect Streamlit dependency in the demo
environment, not an evaluation-core dependency.

The portable command was attempted:

```powershell
py -3.12 -m pip install -e ".[evaluation,demo,dev]"
```

Actual result: exit code 1, `No installed Python found!`, because the managed
environment does not provide the Windows `py` launcher.

The equivalent managed-Python target install was then run against `.venv`:

```powershell
& "<managed-python>\python.exe" -m pip --python .\.venv install -e ".[evaluation,demo,dev]"
```

Actual result: success; `financial-rag-platform` was rebuilt as an editable
install and all required dependencies were already satisfied.

For a normal local Windows Python installation:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[api,models,evaluation,demo,dev]"
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
- Ruff format: 151 files already formatted.
- Mypy strict: no issues in 124 source files.
- Pytest: 181 passed, 1 skipped.
- Branch-enabled total coverage: 90%.
- The one skip remains the opt-in migrated PostgreSQL test because
  `TEST_DATABASE_URL` is not configured.
- No automated test made a live HTTP, OpenAI, model-download, or database call.

The import/OpenAPI smoke reported seven paths, including the new evaluation
endpoint. The CLI help command completed successfully.

A final Streamlit `AppTest` reported:

```text
exceptions: 0
title: Financial Document Intelligence
tabs: Ask, Compare retrieval, Evaluate, Current scope
file uploaders: 1
```

A hidden Streamlit process was started on `127.0.0.1:8512`.
`/_stcore/health` returned HTTP 200 with body `ok`. The exact process was stopped
and a final port check confirmed that no listener remained.

## Publication and immutable artifacts

The only checked-in benchmark content is synthetic and contains no real company,
filing, FinanceBench, or source-document text. No evaluation report was written
outside pytest's ignored temporary directory.

Final checks cover ignored `.env`, FinanceBench data, PDFs, embeddings/indexes,
evaluation-run output, and all 15 notebooks; a credential-pattern scan excludes
the restricted data/notebook trees and `.venv`.

No notebook was opened for writing, executed, formatted, moved, or deleted. No
staging, commit, branch, push, move, or deletion was performed.

As in the previous phase, `git status --short --ignored` reports the public
project tree as untracked and local caches/data/notebooks as ignored. The
workspace Git metadata still has no resolvable `HEAD`; this phase did not attempt
to repair repository history or create a commit.

## Known limitations and next boundary

- Relevance requires pre-mapped chunk IDs; there is no evidence-page-to-chunk
  alignment importer yet.
- Evaluation is synchronous and in-memory, with no durable history or resume.
- Answer metrics invoke the existing grounded service, which performs a second
  retrieval pass after the retrieval-metric pass.
- Exact match/token F1 do not assess numeric equivalence, semantic entailment,
  citation precision/recall, or financial correctness.
- No real FinanceBench evaluation was run or claimed.
- RAGAS/RAGChecker remain optional future adapters and must preserve null
  skipped/failed semantics plus full model/package/prompt provenance.
- PostgreSQL evaluation persistence, workers, Docker/Compose, release CI, and
  public deployment remain future work.

Phase 7A/7B stops here for review.
