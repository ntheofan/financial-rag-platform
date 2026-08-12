# Phase 13 report - hosted CI stabilization

Date: 2026-08-12

## Outcome

Phase 13 fixes the two failures observed after publishing the repository:
pytest temporary-directory creation in a clean checkout and Docker layer-cache
use without an explicit Buildx builder. The changes are limited to CI and test
portability. No business logic, public API, research protocol, runtime default,
database schema, or notebook changed.

The project remains **in development**. This phase does not add deployment,
authentication, scalability, benchmark, or production-readiness claims.

## Root causes and changes

### Portable pytest temporary directory

The pytest configuration previously used
`--basetemp=.cache/pytest-tmp`. The ignored `.cache` parent does not exist in a
fresh GitHub checkout, so pytest could not create its temporary tree. Removing
the explicit setting solved that problem on Linux but exposed an unrelated
permission failure in the default Windows temporary directory.

The final configuration uses `--basetemp=.pytest-tmp`. This path is directly
below the repository checkout, so its existing parent is portable across clean
Linux and Windows workspaces. `.pytest-tmp/` is ignored explicitly.

### Explicit Buildx builder

The container job requested the GitHub Actions cache backend without first
creating a Buildx builder. Phase 13 now sets up Buildx explicitly with
`docker/setup-buildx-action@v4` and uses `docker/build-push-action@v7` for all
three image targets. This follows Docker's documented GitHub Actions cache
configuration and avoids relying on the default Docker driver.

### Regression contracts

`tests/test_ci_contracts.py` protects both fixes with static, network-free
tests. It checks that the repository-local pytest temporary path is ignored and
that the workflow creates a current Buildx builder before using the current
build action.

Files changed in Phase 13:

- `.github/workflows/ci.yml`;
- `.gitignore`;
- `pyproject.toml`;
- `tests/test_ci_contracts.py`;
- `docs/phase-13-report.md`.

## Verification

### Python and clean-checkout checks

Commands:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Actual final results:

- `pip check`: `No broken requirements found`;
- Ruff lint: all checks passed;
- Ruff format: `193 files already formatted`;
- mypy: `Success: no issues found in 146 source files`;
- pytest: `235 passed, 1 skipped in 17.15s`;
- combined branch coverage: 87%;
- the deliberate opt-in PostgreSQL integration test remained skipped.

Before the final configuration was selected, a full Windows test run with
pytest's default temporary directory failed with a permission error below
`$env:TEMP`. Two consecutive targeted Windows runs with the final
`.pytest-tmp` configuration passed: `6 passed in 0.03s` and
`6 passed in 0.02s`.

The public-file snapshot was also copied into a disposable
`python:3.12-slim-bookworm` container, installed with `.[demo,dev]`, and tested
using the exact coverage command from CI. Result:
`235 passed, 1 skipped in 21.70s`, with 87% combined branch coverage. The clean
snapshot contained no ignored or private local artifact.

### Docker and Compose checks

A temporary `docker-container` Buildx builder named
`financial-rag-phase13` successfully built all three workflow targets without
pushing images:

- `api`;
- `api-models`;
- `demo`.

The three builds completed successfully in 354 seconds in total. The temporary
builder was then removed. Compose configuration validation also passed:

```powershell
& $docker compose config --quiet
```

### Pre-commit, publication, and source contracts

Commands:

```powershell
$env:PRE_COMMIT_HOME = Join-Path (Get-Location) '.cache\pre-commit'
.\.venv\Scripts\pre-commit.exe run --all-files
.\.venv\Scripts\pre-commit.exe run --hook-stage manual --all-files
.\.venv\Scripts\python.exe scripts\check_publication.py
.\.venv\Scripts\python.exe scripts\check_release_candidate.py
git diff --check
git status --short --ignored
```

Actual results before this report was added:

- standard pre-commit: Ruff lint, Ruff format, and mypy passed;
- manual pre-commit: Ruff lint, Ruff format, mypy, pytest, and publication
  checks passed;
- publication scanner: passed with 218 candidate files inspected;
- all 11 deterministic `platform_rc_v1` source checks passed;
- all 15 protected notebook hashes matched `notebook_hashes_v1`;
- `git diff --check`: passed.

The release-candidate script's host observations still report Docker as absent
because the user-local Docker CLI is not on this PowerShell session's `PATH`.
The explicit Buildx builds and Compose validation above used the discovered CLI
path and are the authoritative Docker results.

## Preserved boundaries

- All 15 thesis notebooks remain byte-for-byte unchanged and ignored.
- No source PDF, FinanceBench artifact, parsed text, chunk, embedding, vector
  index, generated context, local database, model cache, `.env`, or secret was
  added.
- Automated tests made no live OpenAI or model-service call.
- `research_legacy_v1` and `platform_v1` behavior remain unchanged.
- No image was pushed and no service was deployed.

The exact hosted GitHub Actions result belongs to the commit produced after
this report. It is therefore verified and reported after the commit is pushed,
rather than being predicted here.
