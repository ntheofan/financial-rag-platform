# Public release checklist

This is a release gate for the source repository, not approval for public
deployment. A release may describe only the tested local single-user demo.

## Automated gates

The GitHub Actions workflow runs four independent jobs:

1. Release-contract, Ruff, formatting, strict mypy, pytest/coverage, and the
   publication scanner.
2. Alembic plus the opt-in integration test against PostgreSQL 17/pgvector.
3. A strict `pip-audit` resolution of the declared Python runtime dependencies.
4. Compose-model validation plus lightweight API, CPU model-enabled API, and
   Streamlit image builds without pushing images.

Dependabot checks Python, GitHub Actions, and Docker dependencies weekly. It
does not merge changes automatically.

Run the local source gates with:

```powershell
.\.venv\Scripts\python.exe scripts/check_publication.py
.\.venv\Scripts\python.exe scripts/check_release_candidate.py
.\.venv\Scripts\python.exe scripts/check_release_repository.py
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
.\.venv\Scripts\python.exe -m pip_audit --strict .
```

The synthetic end-to-end test is part of the normal pytest run and can also be
isolated with:

```powershell
.\.venv\Scripts\pytest.exe tests/e2e/test_synthetic_recruiter_flow.py -q
```

When Docker is available, also run:

```powershell
docker compose config --quiet
docker build --target api -t financial-rag-api:local .
docker build --target api-models -t financial-rag-api-models:local .
docker build --target demo -t financial-rag-demo:local .
docker compose up --build --wait
docker compose ps
.\.venv\Scripts\python.exe scripts/run_local_acceptance.py
docker compose down
```

## Mandatory manual review

- Review `git status --short --ignored`, the complete staged filename list, and
  the staged diff.
- Confirm `.env`, PDFs, parsed/full text, chunks, embeddings, indexes, contexts,
  local databases, evaluation runs, caches, and Docker volumes are absent.
- Confirm all 15 notebook hashes match the approved immutable baseline. The
  Phase 11 snapshot establishes future equality only; because this workspace
  has no readable historical `HEAD`, obtain explicit approval before treating
  it as the authoritative baseline. The notebooks remain excluded from the
  public candidate unless their separate content review is completed.
- Review README claims, screenshots, logs, reports, and release notes for
  restricted text, local paths, credentials, and unsupported benchmark or
  production claims.
- Review third-party attribution and `DATA_LICENSE.md`.
- Confirm no image or CI artifact contains corpus/model/runtime data.

Do not publish if any check is unavailable or unexplained. Record unavailable
infrastructure checks explicitly; absence of Docker or a database is not a
passing smoke test.

## Phase 10 evidence states

Use only these meanings in reports and release notes:

- **passed:** the exact check ran successfully in the named environment;
- **failed:** the check ran and returned a failure;
- **unavailable:** the prerequisite was absent, so no claim may be made;
- **not run:** the prerequisite may exist, but the check was not executed.

The offline synthetic flow validates composition and contracts, but is not
evidence for pgvector persistence, BGE-M3 quality, OpenAI behavior, container
startup, CI execution, or benchmark performance.

The Phase 11 runner is the blocking real-service proof for those local
composition claims. A runner file or unit-test pass is not acceptance evidence;
only a successful run against the prepared Compose services counts.
