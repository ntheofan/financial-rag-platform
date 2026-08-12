# PostgreSQL, pgvector, and revision storage

## Persistence boundary

The persistence layer adds durable storage beneath the ingestion and retrieval contracts. It does
not expose an API, run ingestion jobs, download models, query OpenAI, generate
answers, execute FinanceBench, or replace the current FAISS/BM25 comparison
routes with database retrieval.

The implementation targets one explicitly configured PostgreSQL database with
the `vector` extension. Importing `financial_rag.storage` neither reads settings
nor opens a connection. The caller must construct `StorageSettings`, an async
engine, a session factory, and `PostgresRevisionStore` explicitly.

## Schema

```text
documents 1---* chunks
    |              |
    |              +---* corpus_revision_chunks *---1 corpus_revisions
    +------------------* corpus_revision_documents ---+
                                                       |
index_revisions *--------------------------------------+
    |
    +---* chunk_embeddings --- corpus revision + chunk membership

corpus_build_jobs --- optional completed corpus/index revision references
```

- `documents` stores portable ingestion source metadata. It never stores an
  absolute local path or a source PDF.
- `chunks` stores exact chunk content and complete page/section lineage.
- `corpus_revisions` identifies a chunking configuration plus an exact ordered
  chunk mapping. Membership tables preserve document membership and row order.
- `index_revisions` identifies one embedding model/configuration and its retrieval
  compatibility fingerprints.
- `chunk_embeddings` stores one `vector(1024)` per ordered chunk. Composite
  foreign keys ensure that a vector cannot point to a chunk outside its corpus
  revision or silently claim another index revision.
- `corpus_build_jobs` stores only status, counts, safe error codes, timestamps,
  and optional revision IDs. It stores no filenames, paths, upload bytes, or
  extracted content.

Chunk text and vectors are prohibited public artifacts even though their schema
is public. Database files, dumps, volumes, logs, and credentials remain ignored.

## Revision lifecycle

Corpus revision IDs are deterministic hashes over the ordered `ChunkRecord`
payload and chunking-configuration fingerprint. Index revision IDs are
deterministic hashes over the corpus revision ID and the timestamp-independent
retrieval manifest identity.

The current single-user store writes a complete revision transactionally and
publishes it directly as `ready`. Repeating the exact operation is idempotent.
Conflicting content under an existing document/chunk identity fails explicitly.
There are no in-place content or vector updates. A change to source bytes,
chunking, chunk order, model, dimensions, normalization, retrieval configuration,
or vector content produces a new logical revision.

The schema reserves `failed` and `archived` states for future background-job and
retention workflows. The persistence layer does not expose those state transitions and
does not delete revisions.

Before writing an index, the store validates:

- the fixed `platform_v1` dimension of 1,024;
- one finite, non-zero, L2-normalized vector per chunk;
- manifest count, chunk mapping, vector fingerprint, and chunking fingerprint;
- exact equality with the persisted ordered corpus revision.

Loads repeat count, order, normalization, and fingerprint checks before vectors
are returned to application code.

## Local migration workflow

Prerequisites are PostgreSQL with a server-compatible pgvector installation and
a local database/user. Copy `.env.example` to the ignored `.env`, replace the
example `DATABASE_URL`, and never paste a real URL into documentation or logs.

```powershell
py -3.12 -m pip install -e ".[dev]"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
```

To inspect SQL without connecting, provide a synthetic URL through Alembic's
command-line override:

```powershell
.\.venv\Scripts\alembic.exe -x database_url=postgresql+asyncpg://user:password@localhost/db upgrade head --sql
```

Downgrade removes only project-owned tables. It intentionally leaves the
potentially shared `vector` extension installed:

```powershell
.\.venv\Scripts\alembic.exe downgrade base
```

The current Alembic head is `20260812_0002`. An opt-in, read-only infrastructure
test checks the extension and migration
head. It is skipped unless `TEST_DATABASE_URL` is set:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://..."
.\.venv\Scripts\pytest.exe -m integration -q
```

## Deliberate limitations

- No PostgreSQL server or source corpus is bundled, started, or populated.
- CI runs offline unit tests and skips the infrastructure test by default.
- The column is fixed to `vector(1024)` for BGE-M3 and `platform_v1`; another
  embedding dimension requires a reviewed schema migration and new revisions.
- No HNSW/IVFFlat index is claimed. Adding approximate pgvector search would
  require a separate, reproducible comparison against exact `IndexFlatIP`.
- The corpus lifecycle can hydrate exact FAISS/BM25/reranker services from one explicitly
  selected persisted pgvector revision. SQL-native pgvector retrieval and
  approximate indexes remain future work.
- Multi-user isolation, authorization, backups, encryption policy, retention,
  managed PostgreSQL, pooling proxies, monitoring, and scaling are future work.
