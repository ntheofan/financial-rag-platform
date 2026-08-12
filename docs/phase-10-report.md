# Phase 10 report - release-candidate validation

Date: 2026-08-12

## Outcome and scope

Phase 10 adds a source-level release-candidate contract, a safe local preflight,
and a complete offline synthetic recruiter-flow test. It does not add product
features, create a release, change package version `0.1.0`, claim production
readiness, deploy the application, or publish benchmark results.

The source validation is green. The project is **not approved as a fully
validated release candidate** in this environment because Docker/PostgreSQL,
the optional BGE model adapter, the strict project dependency audit, hosted CI,
and notebook-baseline comparison were not successfully exercised.

## Files changed

Added:

- `configs/release/platform_rc_v1.json`
- `scripts/check_release_candidate.py`
- `tests/test_release_candidate.py`
- `tests/e2e/__init__.py`
- `tests/e2e/test_synthetic_recruiter_flow.py`
- `docs/release-candidate.md`
- `docs/phase-10-report.md`

Updated:

- `.github/workflows/ci.yml`
- `README.md`
- `configs/README.md`
- `scripts/README.md`
- `docs/release-checklist.md`

No runtime business module, dependency declaration, migration, database model,
container definition, or Streamlit feature was changed.

## Technical decisions

### Frozen source contract

`platform_rc_v1.json` records only deterministic expectations: development
status, version `0.1.0`, Python 3.12, `platform_v1`, `platform_eval_v1`,
`local_v1`, Alembic head `20260812_0002`, 12 API paths, the local/public
notebook boundary, and gate names. It stores no result, timestamp, machine
path, secret, or approval claim.

The preflight parses migration metadata with Python's AST rather than importing
or executing migration modules. It builds OpenAPI from the side-effect-free app
factory and counts notebook filenames without reading notebook contents.

Infrastructure checks report only capability presence. They never print a
database URL or secret, connect to PostgreSQL, load model weights, invoke
OpenAI, or start Docker. Default mode fails on source drift; strict mode also
fails when the infrastructure prerequisites are unavailable.

### Synthetic end-to-end validation

The new ASGI test exercises the real upload route, staging, ingestion,
normalization, chunking, metadata lineage, indexing orchestration, activation,
dense/Hybrid/Hybrid+Reranker retrieval, citation-validated grounded generation,
and paired evaluation.

It uses generated Markdown bytes, deterministic fake embeddings/reranking/
generation, and a test-only in-memory revision adapter. The adapter implements
the same ports and validates deterministic revision/vector fingerprints, but it
is explicitly not PostgreSQL or pgvector evidence.

### CI and release language

The existing quality job now runs the release source-contract check. Release
documentation defines `passed`, `failed`, `unavailable`, and `not run`, and
states what synthetic validation cannot prove. README status remains
`in development`.

## Verification results

### Passed

Install:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo,dev,security]"
```

Result: exit 0; editable `financial-rag-platform==0.1.0` built and installed.
All declared packages were already satisfied. Pip's optional latest-version
check emitted a warning, but installation completed successfully.

Focused Phase 10 checks:

```powershell
.\.venv\Scripts\ruff.exe check scripts\check_release_candidate.py tests\test_release_candidate.py tests\e2e
.\.venv\Scripts\mypy.exe scripts\check_release_candidate.py tests\test_release_candidate.py tests\e2e
.\.venv\Scripts\pytest.exe tests\test_release_candidate.py tests\e2e -q
```

Results: Ruff passed; mypy reported no issues in 4 source files; pytest reported
`3 passed`.

Full source suite:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Results:

- Ruff lint: passed.
- Ruff format: `181 files already formatted`.
- mypy: no issues in 142 source files.
- pytest: `219 passed, 1 skipped`.
- combined branch coverage: 87%.
- the skipped test is the opt-in PostgreSQL integration test.

Contract/publication/migration checks:

```powershell
.\.venv\Scripts\python.exe scripts\check_publication.py
.\.venv\Scripts\python.exe scripts\check_release_candidate.py
.\.venv\Scripts\alembic.exe heads
```

Results:

- publication gate: passed; the final post-report run inspected 204 candidate
  files;
- all 11 deterministic release source checks passed;
- local infrastructure observations were `unavailable` for Docker CLI,
  database URL, and FlagEmbedding;
- Alembic reported `20260812_0002 (head)`.

Streamlit structural smoke:

```powershell
@'
from streamlit.testing.v1 import AppTest
app = AppTest.from_file('apps/streamlit_app.py', default_timeout=10).run()
print(f'exceptions={len(app.exception)}')
print('tabs=' + ','.join(tab.label for tab in app.tabs))
print(f'upload_controls={len(app.file_uploader)}')
'@ | .\.venv\Scripts\python.exe -
```

Result: zero exceptions; tabs `Documents`, `Ask`, `Compare retrieval`,
`Evaluate`, `Current scope`; 2 upload controls. Streamlit emitted its expected
bare-mode `ScriptRunContext` warning.

### Expected strict-preflight failure

```powershell
.\.venv\Scripts\python.exe scripts\check_release_candidate.py --require-infrastructure
```

Result: exit 1 because Docker CLI, a database URL, and FlagEmbedding were
unavailable. This is correct strict behavior and is not recorded as a passing
infrastructure validation.

### Dependency audit unavailable

```powershell
.\.venv\Scripts\python.exe -m pip_audit --strict --cache-dir .cache\pip-audit .
.\.venv\Scripts\python.exe -m pip_audit --strict --local --cache-dir .cache\pip-audit
```

The project audit exited 1 before querying vulnerabilities because its
temporary environment could not complete `ensurepip`. The local fallback also
exited 1 with an OpenSSL runtime error. Therefore no local vulnerability-audit
pass is claimed. The unchanged Linux GitHub Actions audit remains a required
blocking gate.

### Not run or unavailable

- Docker/Compose commands: unavailable because no Docker CLI was installed.
- PostgreSQL 17/pgvector migration and runtime smoke: not run; no database URL
  was configured.
- BGE-M3 embedding/reranking model smoke: not run; the optional model adapter
  was unavailable.
- live OpenAI generation: intentionally not run.
- GitHub Actions: not run from this local workspace.
- notebook hash comparison: not run because Git has no readable committed
  baseline; only the 15-file inventory was checked.

## Repository and publication boundary

The final `git status --short --ignored` still reports the public tree as
untracked because this workspace has no readable `HEAD`. That pre-existing Git
state was not repaired. Runtime caches, `.coverage`, `.venv`, all 15 notebooks,
notebook figures, source PDFs, FinanceBench files, parsed/cleaned text, chunks,
embeddings, results, and other research artifacts remain ignored.

No notebook was changed, moved, executed, or formatted. No source PDF, parsed
text, chunk export, embedding/index, generated context, database, model cache,
`.env`, FinanceBench artifact, secret, or real benchmark result was added.

No Git commit was created.

## Remaining release gates

Before any public source release, run the full sequence in
`docs/release-candidate.md` on a prepared machine, obtain a green GitHub Actions
run for the exact commit, compare notebook hashes to an approved baseline, and
complete the manual staged-diff/publication/attribution review.

Public deployment, authentication, multi-user isolation, scaling, managed
storage, distributed job execution, and operational guarantees remain future
work.
