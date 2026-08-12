# Phase 3 report — PostgreSQL/pgvector persistence

Date: 2026-08-01

## Outcome and boundary

Phase 3 implements a small, explicit persistence layer for Phase 1 chunks and
Phase 2 embedding-index manifests. It includes SQLAlchemy 2 async mappings,
PostgreSQL/pgvector storage, Alembic migration infrastructure, deterministic
corpus/index revisions, transactional save/load operations, and compatibility
validation.

It does not include a populated database, a bundled PostgreSQL server, Docker,
an API, database-backed retrieval queries, ingestion jobs, model execution,
OpenAI calls, generation, evaluation, Streamlit, authentication, deployment, or
scaling claims.

## Files changed

Updated foundation and integration files:

- `.env.example`
- `README.md`
- `pyproject.toml`
- `src/financial_rag/core/errors.py`
- `src/financial_rag/domain/__init__.py`
- `src/financial_rag/retrieval/vectors.py`
- `src/financial_rag/storage/__init__.py`

Added persistence implementation:

- `src/financial_rag/domain/revisions.py`
- `src/financial_rag/storage/settings.py`
- `src/financial_rag/storage/database.py`
- `src/financial_rag/storage/models.py`
- `src/financial_rag/storage/revision_store.py`

Added migration infrastructure:

- `alembic.ini`
- `migrations/env.py`
- `migrations/script.py.mako`
- `migrations/versions/20260801_0001_revision_storage.py`

Added documentation and tests:

- `docs/storage-design.md`
- `docs/phase-3-report.md`
- `tests/unit/domain/test_revisions.py`
- `tests/unit/storage/__init__.py`
- `tests/unit/storage/test_settings.py`
- `tests/unit/storage/test_models.py`
- `tests/unit/storage/test_compatibility.py`
- `tests/unit/storage/test_revision_store.py`
- `tests/integration/__init__.py`
- `tests/integration/storage/__init__.py`
- `tests/integration/storage/test_migrated_database.py`

No notebook, source document, dataset artifact, generated chunk corpus, real
embedding, FAISS artifact, database file, dump, model cache, or `.env` was
created or modified.

## Technical decisions

### PostgreSQL-only runtime boundary

`StorageSettings` requires an explicit `postgresql+asyncpg://` URL and stores it
as `SecretStr`. Engine construction is separate and lazy: importing modules or
constructing the engine does not contact a database. Connection data is never
included in structured logs.

SQLAlchemy, Alembic, asyncpg, and pgvector are now runtime dependencies because
storage is implemented application functionality. `aiosqlite` is test-only and
allows the transaction/repository behavior to be executed offline; it is not a
supported application backend.

### Normalized schema and lineage

Seven project tables separate reusable documents/chunks from versioned corpus
membership and embedding indexes. Ordered positions are stored explicitly.
Composite foreign keys prevent embedding rows from referring to a chunk outside
their declared corpus or to a different index/corpus pair.

The vector column is fixed at `vector(1024)`, matching BGE-M3 and `platform_v1`.
The project deliberately does not create HNSW or IVFFlat indexes in this phase,
because that would introduce an approximate retrieval mode without an approved
reproducibility protocol.

### Immutable revisions

Corpus identities hash the ordered full chunk mapping plus the chunking
configuration fingerprint. Index identities hash the corpus identity plus the
timestamp-independent Phase 2 manifest identity. Exact repeated writes are
idempotent. Conflicting document/chunk identities and incompatible manifest,
mapping, chunking, vector, count, or dimension data fail explicitly.

The current single-user operation writes complete revisions atomically as
`ready`; no partially visible revision is exposed. `failed` and `archived` are
reserved schema states only and have no Phase 3 transition workflow.

### Migration behavior

Migration `20260801_0001` creates the `vector` extension when absent and creates
all seven tables, constraints, and relational indexes. Downgrade removes only
project-owned tables and intentionally leaves the potentially shared extension
installed.

## Verification actually performed

### Installation

The requested launcher command was attempted:

```powershell
py -3.12 -m pip install -e ".[dev]"
```

Actual result: exit code 1, `No installed Python found!`.

The existing managed Python 3.12 environment was therefore used to install the
same editable `.[dev]` definition into `.venv`. Actual result: success. Newly
installed Phase 3 packages included SQLAlchemy 2.0.51, Alembic 1.18.5, asyncpg
0.31.0, pgvector 0.5.0, and test-only aiosqlite 0.22.1.

The portable local equivalent when the Python launcher is installed remains:

```powershell
py -3.12 -m pip install -e ".[dev]"
```

### Quality and tests

Commands:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Results before this report-only addition, followed by a final repetition:

- Ruff lint: all checks passed.
- Ruff format: all files formatted after one test file was mechanically fixed.
- Mypy strict: no issues in 71 source files.
- Pytest: 95 passed, 1 skipped.
- Total coverage: 90% with branch coverage enabled.
- The skipped test is the opt-in, read-only PostgreSQL infrastructure test
  because `TEST_DATABASE_URL` was not configured.

The store itself was exercised through synthetic offline transactions for
corpus round-trip ordering, idempotency, identity conflicts, index round-trip,
vector order, and manifest alignment. No real filing content or model vector was
used.

### Alembic and schema

Commands:

```powershell
.\.venv\Scripts\alembic.exe heads
.\.venv\Scripts\alembic.exe -x database_url=postgresql+asyncpg://synthetic:synthetic@localhost/financial_rag upgrade head --sql
.\.venv\Scripts\alembic.exe -x database_url=postgresql+asyncpg://synthetic:synthetic@localhost/financial_rag downgrade head:base --sql
```

Actual results:

- one head: `20260801_0001`;
- offline upgrade SQL generated successfully with transactional PostgreSQL DDL,
  `CREATE EXTENSION IF NOT EXISTS vector`, seven tables, and `VECTOR(1024)`;
- offline downgrade SQL generated successfully in reverse dependency order;
- the environment had neither `psql` nor Docker available, so no claim is made
  that the migration was applied to a live PostgreSQL server.

The import/schema smoke test used Python 3.12.13, imported the public storage
boundary without a connection, and registered all seven expected tables.

### Repository and publication boundary

Final checks include:

```powershell
git status --short --ignored
git ls-files --others --exclude-standard
git check-ignore -v .env pgdata data\processed\synthetic.db
Get-ChildItem notebooks\*.ipynb | Get-FileHash -Algorithm SHA256
```

The 15 notebook hashes remain identical to the Phase 2/audit baseline. Ignored
data, notebooks, environments, caches, coverage files, and database runtime
paths remain outside the public file list. Git still reports `No commits yet on
master`; no staging, commit, branch, deletion, move, or notebook operation was
performed.

## Known limitations and next boundary

- A real PostgreSQL + pgvector migration/integration run still requires an
  explicitly provisioned local test database.
- No database-backed dense-search adapter exists yet; Phase 2 FAISS/BM25 remains
  the retrieval runtime.
- No large-corpus performance or concurrency benchmark was executed.
- Revision archival/deletion and failed background-build lifecycle are not
  implemented.
- Backup, encryption, retention, tenant isolation, managed storage, and
  operational monitoring remain future work.

A subsequent approved phase can add a typed application/API layer over the
existing ingestion, retrieval, and storage services. It should not add answer
generation, evaluation, Docker, or Streamlit unless those are explicitly
included in that phase's agreed scope.

Phase 3 stops here for review.
