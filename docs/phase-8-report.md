# Phase 8 report - local containers and public release gates

Date: 2026-08-12

## Outcome and scope

Phase 8 was implemented in the approved sequence:

1. **8A - local composition:** multi-target non-root images, PostgreSQL 17 with
   pgvector, explicit one-shot Alembic migration, FastAPI, Streamlit, health
   checks, loopback ports, and isolated local volumes;
2. **8B - CI/publication hardening:** independent quality, pgvector integration,
   dependency-audit, publication, Compose-validation, and image-build jobs,
   plus Dependabot and a local publication scanner.

No ingestion, retrieval, generation, evaluation, API, or database business
logic changed. No image was pushed, no service was deployed, and no Git stage,
commit, branch, or push was performed.

This remains a local, single-user recruiter demo. The work does not add or claim
authentication, public hosting, tenant isolation, scaling, managed storage,
durable jobs, or production operations.

## Files changed

Added container composition:

- `.dockerignore`
- `Dockerfile`
- `compose.yaml`

Added CI and publication controls:

- `.github/dependabot.yml`
- `scripts/__init__.py`
- `scripts/check_publication.py`
- `tests/test_publication_gate.py`
- `tests/test_container_contracts.py`

Added documentation:

- `docs/architecture.md`
- `docs/container-runtime.md`
- `docs/release-checklist.md`
- `docs/phase-8-report.md`

Updated existing project boundaries and instructions:

- `.env.example`
- `.github/workflows/ci.yml`
- `.pre-commit-config.yaml`
- `pyproject.toml`
- `README.md`
- `docs/publication-policy.md`
- `scripts/README.md`

## 8A technical decisions

The root Dockerfile has three explicit final targets:

- `api`: lightweight API/Alembic image with `.[api]`, used by migrations and CI;
- `api-models`: API plus `.[models]`, used by the real local Compose service;
- `demo`: Streamlit plus HTTP client dependencies only.

All application targets use Python 3.12, UID/GID `10001`, no bytecode or pip
cache, and no source documents or model weights. Compose additionally gives the
API and demo a read-only root filesystem, drops all Linux capabilities, enables
`no-new-privileges`, and supplies only a temporary `/tmp` mount where needed.

PostgreSQL uses the explicit
`pgvector/pgvector:0.8.2-pg17-bookworm` tag. Its host port, and both application
ports, bind to `127.0.0.1`. Database state and model cache use named volumes.
The ignored `./artifacts` host directory is mounted read-only.

The `migrate` service waits for PostgreSQL health, executes `alembic upgrade
head`, and exits. FastAPI waits for that successful exit and does not own or
implicitly execute schema migration. Streamlit waits for FastAPI liveness and
uses only the HTTP boundary.

Retrieval artifacts remain opt-in. With
`CONTAINER_RETRIEVAL_ARTIFACT_DIRECTORY` blank, the stack honestly exposes
liveness/OpenAPI/infrastructure capability while retrieval, generation, and
evaluation remain unavailable. Setting it to `/runtime/artifacts` requires a
compatible ignored Phase 2 artifact. Generation separately requires a real key
only in ignored `.env`.

`.dockerignore` excludes Git metadata, local environment files, data, notebooks,
artifacts, evaluations, databases, logs, model caches, vector/index formats, and
source PDFs from every build context. Model libraries may be installed, but
weights are not copied into an image.

## 8B technical decisions

The GitHub Actions workflow now has four independent, blocking jobs:

- Python 3.12 source quality, coverage, and publication boundary;
- PostgreSQL 17/pgvector migration plus the existing opt-in integration test;
- strict project dependency-resolution `pip-audit`;
- `docker compose config` plus lightweight API/demo image builds with no push.

The model-enabled target is deliberately not built in CI because its model
dependency stack is large; CI verifies the same project/API packaging through
the lightweight `api` target. No workflow receives `OPENAI_API_KEY`, invokes a
model, downloads model weights, calls OpenAI, or uploads a corpus/report/image.

Dependabot proposes weekly Python, GitHub Actions, and Docker dependency
updates; it has no auto-merge configuration.

`scripts/check_publication.py` deterministically inspects Git-tracked and
non-ignored untracked candidates. It rejects restricted data/runtime roots,
unreviewed notebooks, FinanceBench artifacts, risky binary/vector/database
types, symlinks, files over 10 MiB, common credential patterns, and local home
paths. It prints only filenames and safe reason labels. Synthetic fixture PDFs
under `tests/fixtures/` retain the existing narrow policy exception. Unit tests
exercise both allowed and rejected cases.

The scanner is a conservative first pass, not a replacement for staged-diff,
notebook-baseline, license, screenshot, log, or claim review.

## Installation and checks actually performed

The direct virtual-environment install was attempted:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[security,demo,dev]"
```

Actual result: exit code 1 because this managed `.venv` has no embedded `pip`
module.

The established workspace-managed installer was then used (the private host
path is intentionally represented by a public-safe placeholder):

```powershell
& "<managed-python>\python.exe" -m pip --python .\.venv install -e ".[security,demo,dev]"
```

Actual result: success. The editable project was rebuilt and `pip-audit 2.10.1`
plus its dependencies were installed.

Static YAML loading was run for `compose.yaml`, `.github/workflows/ci.yml`, and
`.github/dependabot.yml`:

```powershell
.\.venv\Scripts\python.exe -c "<load the three files with yaml.safe_load>"
```

Actual result: all three documents parsed as mappings. The Docker-free
container contract tests also passed.

Final source verification commands:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
.\.venv\Scripts\python.exe scripts/check_publication.py
```

Final results after the report was added:

- Ruff lint: all checks passed.
- Ruff formatting: all files already formatted.
- Strict mypy: no issues in 126 source files.
- Pytest: 190 passed, 1 skipped.
- Branch-enabled package coverage: 90%.
- The one skip is the opt-in migrated PostgreSQL test because
  `TEST_DATABASE_URL` is absent locally.
- Publication gate: passed for 181 candidate files.
- No automated test made a live model, OpenAI, HTTP, or database call.

An import/OpenAPI smoke loaded package version `0.1.0`, constructed the local
application without entering its lifespan, and reported the existing seven API
paths. It made no model, network, artifact, or database call.

## Checks unavailable in this environment

The following commands were attempted:

```powershell
docker version
docker compose version
```

Actual result: both failed because `docker` is not installed or available on
`PATH`. Therefore no local Compose config, image build, container health,
Alembic-on-container, pgvector-container, or end-to-end container smoke is
claimed. Those checks are encoded in CI and remain mandatory before release on
a Docker-capable machine.

The dependency audit was attempted for both the managed environment and the
declared local project:

```powershell
.\.venv\Scripts\python.exe -m pip_audit --strict .
.\.venv\Scripts\python.exe -m pip_audit --strict --cache-dir .cache\pip-audit .
```

The environment-default attempt could not create the managed runtime's
user-cache directory; a workspace-local-cache environment retry failed in the
bundled Windows TLS runtime with `OPENSSL_Applink`; and project dependency
resolution could not bootstrap pip in its temporary managed virtual
environment. These are unavailable audits, not a clean audit and not reported
vulnerabilities. The Linux CI project audit remains strict/blocking.

GitHub Actions itself was not executed locally. Workflow presence is not
reported as a passing remote CI run.

## Publication and immutable artifacts

`git check-ignore -v` confirmed ignore rules for `.env`, FinanceBench JSONL,
FAISS artifacts, model weights, evaluation runs, and a thesis notebook. The
publication scanner passed after all Phase 8 files were present.

SHA-256 hashes were computed read-only for all 15 notebooks. No notebook was
opened for writing, executed, formatted, moved, deleted, staged, or published.
Because the current Git metadata still has no resolvable `HEAD`, this phase
cannot independently compare them to a committed baseline; the manual baseline
comparison remains a release prerequisite.

`git status --short --ignored` continues to report the public project tree as
untracked and the restricted local data, notebooks, environments, caches, and
generated artifacts as ignored. Phase 8 did not repair Git history or create a
commit.

## Exact commands for a normal local checkout

Install and run source checks:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[security,demo,dev]"
.\.venv\Scripts\python.exe scripts/check_publication.py
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
.\.venv\Scripts\python.exe -m pip_audit --strict .
```

On a Docker-capable machine, validate and start the local stack:

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker build --target api -t financial-rag-api:local .
docker build --target demo -t financial-rag-demo:local .
docker compose up --build --wait
docker compose ps
docker compose down
```

Do not set the artifact path or OpenAI key unless those capabilities are needed.
Keep the resulting `.env`, `artifacts/`, database volume, and model cache local.

## Next boundary

The most valuable next phase is a safe local document/corpus lifecycle: bounded
upload/import, explicit indexing jobs, progress/error state, revision selection,
and UI/API controls backed by the existing ingestion, retrieval, and persistence
services. That phase must decide durable job semantics and data-retention rules
before implementation. It must not be conflated with public deployment.

Phase 8A/8B stops here for review.
