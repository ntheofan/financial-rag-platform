# Phase 11 report - local acceptance and release preparation

Date: 2026-08-12

## Outcome

Phase 11A and 11B tooling and documentation are complete. The source suite and
public-boundary checks pass, but the repository is **not release-approved** and
the real local acceptance is **not passed** in this environment.

Blocking facts:

- Docker CLI is unavailable;
- no database URL or ignored `.env` is configured;
- the real FastAPI service is not running, so acceptance returns
  `api_unreachable`;
- the optional model runtime cannot be validated with this bundled Windows
  Python/OpenSSL environment;
- the strict dependency audit cannot create its isolated environment;
- Git `HEAD` does not resolve and all 216 public candidates are untracked;
- GitHub Actions has not run on an exact commit.

No tag, release, commit, push, deployment, production claim, or benchmark claim
was created.

## 11A - real local acceptance

Added:

- `configs/release/local_acceptance_v1.json`
- `tests/fixtures/demo/acme-2025-10k.md`
- `scripts/run_local_acceptance.py`
- `tests/test_local_acceptance.py`
- `docs/local-acceptance.md`

The 1,168-byte Markdown fixture is original synthetic content about fictional
ACME values. It contains no source filing, FinanceBench row, extracted text, or
real financial result.

The runner accepts only an HTTP loopback API and only a Markdown/text file
directly below `tests/fixtures/demo`. It requires revisions/indexing before
upload and every capability after activation. It then checks:

1. bounded upload and completed durable job;
2. corpus and index revision IDs;
3. successful Dense, Hybrid, and Hybrid + Reranker results;
4. source lineage back to the checked fixture;
5. a non-abstained grounded answer with citations;
6. a complete three-mode `platform_eval_v1` evaluation.

The stdout contract contains only safe status/error codes, opaque IDs, counts,
and mode names. It does not write an evidence file or print source text,
answers, contexts, prompts, vectors, paths, credentials, or database values.

The runner disables TLS verification only inside its HTTP-only loopback client.
Non-loopback and HTTPS targets are rejected before client construction. The
normal Streamlit client retains verified HTTP(S) defaults.

## Import isolation correction

Installing the optional model stack exposed eager package-import behavior:
importing an API schema loaded the FastAPI app, indexing service, LangChain text
splitters, and therefore `sentence_transformers`/Torch when available.

`financial_rag.api`, `financial_rag.indexing`, and `financial_rag.chunking` now
preserve their public exports through lazy module attributes with static
`TYPE_CHECKING` declarations. A subprocess test confirms that importing API
schemas and the demo client does not load `torch`, `FlagEmbedding`, or `openai`.

The optional `models` extra now constrains `sentence-transformers>=2.7,<3`.
This tested bound restored side-effect-free API import after the optional model
dependencies were installed; newer 3.x/5.x variants eagerly imported training
and dataset stacks during ordinary API composition.

This bound is an import compatibility decision, not a retrieval-quality claim.
No live model inference or model-weight download succeeded in this environment.

## 11B - public release preparation

Added:

- `configs/release/notebook_hashes_v1.sha256`
- `scripts/check_release_repository.py`
- `tests/test_release_repository.py`
- `tests/test_import_isolation.py`
- `docs/recruiter-demo.md`
- `docs/release-notes-v0.1.0-draft.md`
- `docs/phase-11-report.md`

Updated:

- `configs/release/platform_rc_v1.json`
- `.github/workflows/ci.yml`
- `README.md`
- `pyproject.toml`
- `src/financial_rag/api/__init__.py`
- `src/financial_rag/indexing/__init__.py`
- `src/financial_rag/chunking/__init__.py`
- `src/financial_rag/demo/client.py`
- `configs/README.md`
- `scripts/README.md`
- `docs/release-candidate.md`
- `docs/release-checklist.md`
- `docs/phase-10-report.md`

The repository gate checks resolvable `HEAD`, tracked public files, staged and
unstaged changes, the publication scanner, and the notebook snapshot. It is
read-only and prints no commit SHA or file content.

`notebook_hashes_v1.sha256` was created from the 15 local files on 2026-08-12.
It verifies future equality to this snapshot only. It cannot prove historical
equality to an earlier thesis baseline because no readable committed `HEAD`
exists. The snapshot requires explicit owner approval before it becomes the
authoritative baseline.

The gate accepts two policy-compliant states: zero notebook artifacts in a
public clone, or all 15 matching notebooks in the local research worktree. A
partial inventory or changed hash fails. The notebooks remain ignored and are
not approved for public publication.

CI now runs both the Phase 10 source contract and the exact-commit repository
contract. The release notes remain explicitly draft.

## Verification

### Install and dependency consistency

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo,dev,security]"
.\.venv\Scripts\python.exe -m pip check
```

Results: editable package installation passed; `pip check` reported
`No broken requirements found`.

### Focused Phase 11 tests

```powershell
.\.venv\Scripts\pytest.exe tests\test_import_isolation.py tests\test_local_acceptance.py tests\test_release_repository.py tests\test_release_candidate.py -q
```

Result: `13 passed` during the focused verification. Earlier focused runs also
validated 9 acceptance/repository/import tests before the updated candidate
inventory test was included.

### Full source suite

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Final post-report verification results:

- Ruff lint: passed;
- Ruff format: 191 files already formatted;
- mypy: no issues in 145 source files;
- pytest: `230 passed, 1 skipped`;
- combined branch coverage: 87%;
- the skipped test remains the opt-in PostgreSQL integration test.

### Source/publication/migration/UI gates

```powershell
.\.venv\Scripts\python.exe scripts\check_publication.py
.\.venv\Scripts\python.exe scripts\check_release_candidate.py
.\.venv\Scripts\alembic.exe heads
```

Final results:

- publication gate passed with 216 candidates;
- all 11 deterministic source-contract checks passed;
- infrastructure observations reported Docker, database URL, and model adapter
  package unavailable;
- Alembic reported `20260812_0002 (head)`.

Streamlit `AppTest` reported zero exceptions, tabs `Documents`, `Ask`,
`Compare retrieval`, `Evaluate`, `Current scope`, and 2 upload controls. It
emitted only the expected bare-mode `ScriptRunContext` warning.

### Repository gate - failed as expected

```powershell
.\.venv\Scripts\python.exe scripts\check_release_repository.py
```

Result: exit 1. `git_head` failed because `HEAD` does not resolve and
`public_files_tracked` failed with 216 non-ignored untracked candidates.
Staged/unstaged tracked-change checks passed, publication found zero violations,
and all 15 notebook hashes matched `notebook_hashes_v1`.

This is not an exact-commit release candidate until the owner establishes the
intended Git baseline and runs the gate again.

### Real local acceptance - failed as expected

```powershell
.\.venv\Scripts\python.exe scripts\run_local_acceptance.py
```

Result: exit 1 with only:

```json
{"error_code":"api_unreachable","schema_version":"local_acceptance_result_v1","status":"failed"}
```

No API request succeeded, no upload occurred, and no data/revision was created.

### Optional model investigation - failed/unavailable

The following was attempted with `HF_HOME` inside ignored `.cache` and telemetry
disabled:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[models]"
```

The first attempt timed out after 120 seconds during installation. A second
cached attempt installed FlagEmbedding 1.4.0 and its dependencies. Import tests
showed:

- latest `sentence-transformers 5.7` / `transformers 5.15` caused ordinary API
  imports to enter the training/datasets dependency graph and fail;
- `transformers 4.x` alone and `sentence-transformers 3.x` did not restore the
  API import;
- `sentence-transformers 2.7` restored API import isolation;
- direct `FlagEmbedding` import still failed in the bundled Windows runtime at
  `aiohttp`/OpenSSL initialization, including after an `aiohttp 3.13` trial.

The optional stack installed during the investigation was removed from the
ignored `.venv`; the normal dependency graph again passes `pip check`. No model
weights were downloaded and `.cache/huggingface` does not exist. Therefore no
BGE embedding or reranker smoke pass is claimed. The model-enabled Linux
Compose build remains a blocking external gate.

### Dependency audit - unavailable

```powershell
.\.venv\Scripts\python.exe -m pip_audit --strict --cache-dir .cache\pip-audit .
```

Result: exit 1 before a vulnerability query because `pip-audit` could not run
`ensurepip` in its temporary environment. No audit pass is claimed. The Linux
CI audit remains blocking.

### Infrastructure and hosted CI - unavailable/not run

- Docker CLI/Compose: unavailable;
- PostgreSQL 17/pgvector runtime and migration smoke: not run;
- real BGE-M3 embedding/reranker inference: not run;
- live OpenAI grounded generation: intentionally not called here; no `.env` or
  key was configured;
- GitHub Actions: not run because there is no exact commit to push;
- image builds and full Compose readiness/shutdown: not run.

## Publication boundary and unchanged material

`git status --short --ignored` confirms that `.cache`, `.coverage`, virtual
environment, research data, parsed/cleaned text, chunks, embeddings, evaluation
results, source PDFs, all 15 notebooks, and notebook figures remain ignored.

No notebook was opened by project code, changed, moved, executed, or formatted.
The only operation on them was a read-only SHA-256 computation. No source PDF,
parsed text, chunk/index/vector, generated context, database, model weight,
`.env`, secret, FinanceBench artifact, or real result was added.

No Git commit was created.

## Required next actions before `v0.1.0`

1. Establish the intended Git baseline and explicitly approve the notebook hash
   snapshot/publication decision.
2. Run every source and repository gate on a clean exact commit.
3. Run Docker Compose plus `run_local_acceptance.py` successfully on a supported
   model-enabled environment using only the cleared synthetic fixture.
4. Obtain green PostgreSQL/pgvector, dependency-audit, container-build, quality,
   and repository jobs in GitHub Actions for that exact commit.
5. Complete manual staged diff, attribution, claims, screenshot/log, and release
   notes review.
6. Only then create a tag or publish `v0.1.0`.

Public deployment remains out of scope.

## Local acceptance follow-up - 2026-08-12

Docker Desktop became available after the initial Phase 11 report. The
following results supersede the earlier `api_unreachable` infrastructure
observation, but they do **not** make the release candidate ready.

### Environment and Compose bootstrap

- Docker client/server `29.6.2` and Docker Compose `v5.3.1` were detected from
  the user-local Docker Desktop installation.
- `docker compose config --quiet` passed.
- Host port `5432` could not be bound by Docker even though Windows reported no
  listener or excluded range. The already configurable override
  `POSTGRES_PORT=55432` was used; container-to-container PostgreSQL traffic
  remained on port `5432`.
- The database became healthy, the migration job exited `0`, the API became
  healthy, and the Streamlit health endpoint returned `200 ok`.
- PostgreSQL reported Alembic revision `20260812_0002`. Migration logs showed
  both migrations applied in order.
- The model-enabled API image built successfully. A source-only rebuild took
  `438.7s`; the resolved Linux PyTorch dependency also included CUDA 13
  packages. CPU-only dependency resolution and Docker layer caching remain
  packaging-efficiency work, not completed claims.

### Defects found and corrected

The first real corpus build failed with sanitized code `embedding_failed`.
An in-container synthetic probe exposed a permission error under
`/var/cache/financial-rag/huggingface`: the hardened UID `10001` could not
write into the newly mounted model-cache volume.

`Dockerfile` now creates the exact Hugging Face cache directory with ownership
`10001:10001` before switching to the non-root runtime user. The static
container contract test enforces this invariant. The already-created local
volume was repaired idempotently with a one-off root container granted only
temporary `CAP_CHOWN`; no volume was deleted.

After that correction, a real BAAI/bge-m3 CPU probe over a synthetic query
passed with a finite vector of shape `(1024,)`. Model weights were stored only
in the Docker named volume, never in the repository.

The next corpus build reached PostgreSQL and failed with sanitized code
`persistence_failed`. PostgreSQL logs showed that
`corpus_revision_chunks` was inserted before its `corpus_revisions` parent had
been flushed, causing a foreign-key violation. `PostgresRevisionStore` now
flushes each corpus/index parent row before adding its dependent membership or
embedding rows. SQLite foreign-key enforcement is enabled in the repository
unit-test fixture so this ordering regression is caught offline.

Targeted verification after these changes:

```text
ruff: All checks passed!
mypy: Success: no issues found in 2 source files
pytest: 6 passed in 1.42s
```

### Real pipeline evidence after the corrections

The subsequent synthetic build completed and logged:

- one document ingested and one chunk produced with the configured
  `1500`/`200` chunking parameters;
- corpus revision `corpus_a656dfe7029f7d7cc25cdbf4cdb61485` persisted;
- index revision `index_df26930083ba800c323f53f77a8e08b6` persisted with
  one 1024-dimensional vector;
- upload staging removed after completion;
- `retrieval`, `evaluation`, `revisions`, and `indexing` all reported `ready`.

Real dense and hybrid retrieval both returned the same lineage-preserving
synthetic chunk. Dense reported score `0.6350969076156616`; hybrid additionally
reported RRF score `0.03870967741935484`.

The first real `hybrid_reranked` request caused the HTTP connection to close
while the reranker model was loading, after which the Docker daemon reported
`Docker Desktop is unable to start`. Resource exhaustion is a plausible
inference, but an OOM flag could not be read after the daemon failure, so no
root-cause or reranker pass is claimed.

### Remaining acceptance blockers

- No ignored `.env` exists, so generation correctly reports `unavailable`.
  The full acceptance stopped at `required_component_unavailable`; no OpenAI
  request was made and no key was exposed.
- Real BGE reranker inference and Docker stability must pass before the three
  retrieval modes can be claimed as locally accepted.
- Grounded generation/citations and the full paired acceptance require the
  owner to configure `OPENAI_API_KEY` locally without sharing it in logs or
  chat.
- Repository exact-commit and GitHub Actions gates remain unchanged: `HEAD`
  still needs an explicitly approved public baseline commit.

### Full source and repository checks after the follow-up

```text
ruff check .: All checks passed
ruff format --check .: 191 files already formatted
mypy src tests: Success, 145 source files
pytest with coverage: 230 passed, 1 skipped in 19.46s; total coverage 87%
publication gate: passed, 216 candidate files inspected
release source contract: passed; all 11 deterministic source checks passed
repository gate: failed; unresolved HEAD and 216 non-ignored untracked files
notebook integrity: 15 hashes matched notebook_hashes_v1
```

The release source checker still reports Docker unavailable because the
user-local Docker CLI is not on this PowerShell session's `PATH`; the concrete
Docker checks above used the discovered absolute CLI path. This distinction is
recorded rather than silently changing the host environment.

No notebook was modified, moved, executed, or formatted during this follow-up.
No source PDF, private dataset content, parsed corpus, vector/index artifact,
database, model weight, `.env`, or secret was added to the repository. No Git
commit was created.

## Final local acceptance pass - 2026-08-12

After Docker Desktop was restarted and the owner configured the ignored local
`.env`, the remaining runtime gates were completed.

The checked-in `local_v1` runtime now selects CPU explicitly for both BGE
adapters and uses inference batch size `1`. This is local-demo memory hardening;
the BAAI/bge-m3 and BAAI/bge-reranker-v2-m3 model identities, retrieval
configuration, ranking semantics, and thesis chunking defaults are unchanged.
The public and runtime OpenAI default was corrected from the placeholder
`gpt-5.6-luna` to the thesis model `gpt-4o-mini`.

Because a real ignored `.env` now exists, runtime unit tests also gained an
explicit environment-isolation fixture. Those tests change into a synthetic
temporary directory and remove only the relevant environment variable names,
so automated tests cannot discover or use a developer's API key. No automated
test performs a live OpenAI request.

The final real command was:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_acceptance.py
```

Result: exit `0` in `78.9s` with minimized evidence:

```json
{
  "citation_count": 1,
  "corpus_revision_id": "corpus_a656dfe7029f7d7cc25cdbf4cdb61485",
  "dense_chunk_count": 1,
  "evaluation_completed_modes": [
    "dense",
    "hybrid",
    "hybrid_reranked"
  ],
  "hybrid_chunk_count": 1,
  "index_revision_id": "index_df26930083ba800c323f53f77a8e08b6",
  "reranked_chunk_count": 1,
  "schema_version": "local_acceptance_result_v1",
  "status": "passed"
}
```

The opaque per-run job identifier is intentionally omitted from this durable
report. The pass confirms the cleared synthetic path through upload,
normalization/chunking, BGE-M3 embedding, PostgreSQL/pgvector persistence,
activation, Dense, Hybrid, Hybrid + Reranker, grounded OpenAI generation with a
citation, and paired retrieval evaluation across all three modes. It is not a
FinanceBench score or a public-deployment claim.

Final services were healthy: PostgreSQL on the local host override `55432`,
FastAPI on `8000`, and Streamlit on `8501`; the migration job exited `0`.

Final source verification after all follow-up changes:

```text
ruff check .: All checks passed
ruff format --check .: 191 files already formatted
mypy src tests: Success, 145 source files
pytest with coverage: 231 passed, 1 skipped in 16.79s; total coverage 87%
publication gate: passed, 216 candidate files inspected
.env Git status: ignored
```

The local runtime acceptance gate is now passed. Release publication remains
blocked by the unresolved Git baseline (`HEAD` does not exist), the unrun
exact-commit GitHub Actions jobs, and the required manual release review. No
commit, tag, push, or deployment was performed.
