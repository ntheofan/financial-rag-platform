# Phase 14 report - v0.1.0 portfolio release candidate

Date: 2026-08-12

## Outcome

Phase 14 prepares a recruiter-facing `v0.1.0` source release candidate without
creating a tag or GitHub Release. A fresh isolated Docker Compose stack passed
the real synthetic workflow, all five Streamlit views were exercised through
the browser, one observed job-status UX issue was fixed, and the demo now ships
with a benchmark that is contract-aligned with its public synthetic document.

The project remains **in development** and local/single-user only. This phase
does not claim public deployment, production readiness, financial correctness,
or FinanceBench performance.

## Changes

### Recruiter workflow

- Added `tests/fixtures/demo/acme-benchmark.json`, an original synthetic
  two-query benchmark for the existing ACME fixture.
- Added a test that rebuilds the ACME chunks and verifies every benchmark
  relevance identifier against the deterministic output.
- Updated the recruiter walkthrough with exact document and benchmark paths.
- Updated the README with the matching fixtures and current verification
  counts.

### Small UI correction

The Documents view previously kept the initially submitted job snapshot in
session state. After the backend completed the build, refreshing the job list
could therefore leave the separate “Submitted job” caption visibly marked
`pending` while a ready index was already selectable.

`refresh_submitted_job` is a pure presentation helper that replaces only the
matching submitted snapshot with the newest backend entry. The rebuilt UI was
then retested and displayed `completed` immediately after refresh. Retrieval,
indexing, storage, API, and protocol behavior did not change.

### Release documentation

- Added `CHANGELOG.md` with the `v0.1.0` entry.
- Added `docs/release-notes-v0.1.0.md` as the reviewed release notes.
- Updated `apps/README.md`, `README.md`, and `docs/recruiter-demo.md`.
- No screenshot or generated answer/context artifact was saved to the
  repository.

Files changed in this phase:

- `README.md`;
- `CHANGELOG.md`;
- `apps/README.md`;
- `apps/streamlit_app.py`;
- `docs/recruiter-demo.md`;
- `docs/release-notes-v0.1.0.md`;
- `docs/phase-14-report.md`;
- `src/financial_rag/demo/__init__.py`;
- `src/financial_rag/demo/presentation.py`;
- `tests/fixtures/demo/acme-benchmark.json`;
- `tests/unit/demo/test_presentation_and_settings.py`.

## Clean real-service acceptance

An isolated Compose project named `financial-rag-p14` was created with new
PostgreSQL and model-cache volumes and loopback-only ports:

- PostgreSQL: `127.0.0.1:55414`;
- FastAPI: `127.0.0.1:18014`;
- Streamlit: `127.0.0.1:18514`.

The initial `docker compose up --build --wait` passed in 153.6 seconds. The
database, API, and demo were healthy and the migration service exited `0`.

The privacy-minimized real-service runner completed in 174.1 seconds with:

- status `passed`;
- one chunk returned by each of Dense, Hybrid, and Hybrid + Reranker;
- one validated citation;
- all three paired evaluation modes completed.

This covered synthetic ingestion, BGE-M3 indexing, PostgreSQL/pgvector
persistence and activation, all retrieval modes, reranking, grounded OpenAI
generation, and retrieval evaluation. It is workflow evidence, not a latency,
quality, or benchmark result.

The final rebuilt stack also passed `docker compose config --quiet`, migration
execution, and health checks. The code-change rebuild completed in 160.6
seconds. After verification, only the temporary `financial-rag-p14`
containers, network, synthetic database volume, and disposable model-cache
volume were removed. The previously running Phase 12 stack was not modified.

## Browser acceptance

The real Streamlit interface was exercised through all five views:

1. **Documents:** the synthetic ACME Markdown file uploaded, built, refreshed,
   exposed a ready index, and activated successfully. After the UI correction,
   the submitted status changed from `pending` to `completed` on refresh.
2. **Ask:** the checked synthetic question returned a non-abstained grounded
   response with one citation and its retrieval trace.
3. **Compare retrieval:** Dense, Hybrid, and Hybrid + Reranker each returned
   the expected synthetic source and exposed the comparison view.
4. **Evaluate:** `acme-benchmark.json` completed two queries in all three modes.
   For this one-chunk synthetic corpus, MRR and configured Hit@K values were 1.
5. **Current scope:** the local, single-user, non-production boundary rendered
   as documented.

Two manual OpenAI requests were made during this phase: one by the explicit
real-service acceptance runner and one by the Ask UI check. Automated tests
used fakes and made no live OpenAI or model-network call. No secret, source
text dump, answer text, generated context, browser screenshot, or runtime log
was added to the public candidate.

## Source and publication verification

Commands:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
$env:PRE_COMMIT_HOME = Join-Path (Get-Location) '.cache\pre-commit'
.\.venv\Scripts\pre-commit.exe run --all-files
.\.venv\Scripts\pre-commit.exe run --hook-stage manual --all-files
.\.venv\Scripts\python.exe scripts\check_publication.py
.\.venv\Scripts\python.exe scripts\check_release_candidate.py
.\.venv\Scripts\python.exe scripts\check_release_repository.py
git diff --check
git status --short --ignored
```

Actual results before this report was added:

- `pip check`: `No broken requirements found`;
- Ruff lint: all checks passed;
- Ruff format: `196 files already formatted`;
- mypy: `Success: no issues found in 146 source files`;
- pytest: `237 passed, 1 skipped in 18.59s`;
- combined branch coverage: 87%;
- standard and manual pre-commit hooks passed, including pytest and the
  publication boundary;
- publication scanner: passed with 222 candidate files inspected;
- all deterministic `platform_rc_v1` source checks passed;
- all 15 notebook hashes matched `notebook_hashes_v1`;
- `git diff --check`: passed.

The direct Windows `pip-audit` attempt failed before resolution because the
bundled Python could not run `ensurepip` inside its temporary audit
environment. The documented fallback ran in a disposable
`python:3.12-slim-bookworm` container with a read-only repository mount and
reported `No known vulnerabilities found` in 33.3 seconds. This is a
point-in-time advisory-database result.

The repository gate intentionally reports the worktree as dirty and three
public files as untracked because Phase 14 is being handed off for review
before any staging or commit. Its publication boundary, notebook hashes,
resolved `HEAD`, and empty-index checks passed. A clean repository-gate result
can only be obtained after an approved commit.

## Preserved boundaries and next decision

- All 15 thesis notebooks remain byte-for-byte unchanged and ignored.
- No `.env`, credential, real filing, FinanceBench artifact, parsed text,
  chunk corpus, embedding, index, context, local database, or model cache was
  added.
- `research_legacy_v1`, `platform_v1`, `platform_eval_v1`, and `local_v1`
  behavior remain unchanged.
- At the time this local verification report was written, no commit, push,
  tag, GitHub Release, image push, or deployment had been made.

After review, the next controlled sequence is: approve the Phase 14 diff,
commit and push it, wait for hosted CI on the exact commit, and only then decide
separately whether to create the `v0.1.0` tag and GitHub Release.
