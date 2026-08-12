# Local corpus and index lifecycle

The corpus lifecycle connects the tested ingestion, chunking, embedding, revision,
retrieval, API, and demo layers into one bounded local workflow.

```text
upload or local folder
  -> server-owned ignored staging
  -> validated text/PDF loaders
  -> Markdown-aware chunking
  -> BGE-M3 dense embeddings
  -> immutable corpus revision
  -> immutable pgvector index revision
  -> compatibility validation
  -> active in-memory FAISS/BM25/reranker query services
```

This is local single-user orchestration. It is not a public upload service or a
distributed job platform.

## Input boundary

The HTTP endpoint accepts `.pdf`, `.md`, and `.txt` only, with these fixed
limits:

- at most 10 files;
- at most 20 MiB per file;
- at most 50 MiB for the complete request;
- filenames up to 255 characters, without paths or control characters;
- unique filenames under case-insensitive comparison.

Client filenames are metadata labels only. Files are written under an explicit
ignored staging root using server-generated names such as `01.pdf`. The job ID
is an opaque UUID-based identifier and encodes no filename or content.

The staging directory is removed after success or failure. Cleanup is restricted
to the exact server-generated job directory below the configured root. A process
crash can leave a staging directory behind; automatic orphan deletion is not
claimed because retention policy and operator recovery require an explicit
future design.

PDF extraction remains PyMuPDF text extraction without OCR. Extension filtering
is implemented, but content-type or file-signature detection is not yet a
malware scanner. Corrupt, password-protected, image-only, empty, unsupported, or
non-UTF-8 input fails through the existing domain errors.

## Job lifecycle

`corpus_build_jobs` stores only:

- opaque job ID;
- optional user label;
- input file count;
- `pending`, `running`, `completed`, or `failed` status;
- resulting corpus/index revision IDs;
- safe error code;
- timestamps.

It never stores raw upload bytes, filenames, client paths, extracted text,
chunks, vectors, provider responses, or exception messages. Only one job can be
pending/running in the local application instance. A restart marks durable
non-terminal jobs `failed` with `runtime_interrupted`; execution is not resumed.

The HTTP response is `202 Accepted`, after which a FastAPI/Starlette in-process
background task performs the build. This is intentionally smaller than a worker
system, but it means jobs are not resumable, cancellable, or distributed and
progress is status-level rather than per-stage percentage.

## Revision and activation semantics

The existing deterministic document/chunk IDs and fingerprints remain
unchanged. A build:

1. creates validated `ChunkRecord` objects in deterministic order;
2. embeds them with the configured `platform_v1` provider;
3. calculates mapping/vector/configuration fingerprints;
4. persists an idempotent immutable corpus revision;
5. persists an aligned immutable pgvector index revision;
6. reloads and revalidates the persisted records/vectors;
7. creates the in-memory FAISS `IndexFlatIP`, BM25, and optional reranker services;
8. replaces the local single-user query service bundle and completes the job.

Activation rejects mismatched status, embedding model, dimension,
normalization, retrieval configuration, or chunk mapping. Selecting an existing
ready index performs the same validation. Selection is process-local and is not
restored automatically after restart; the user may select it again through the
API or Streamlit.

## API

```text
POST /api/v1/corpus-jobs
GET  /api/v1/corpus-jobs
GET  /api/v1/corpus-jobs/{job_id}
GET  /api/v1/corpora
GET  /api/v1/indexes
POST /api/v1/indexes/{index_revision_id}/activate
```

Existing metadata-by-ID endpoints remain available. List and job responses
never return chunk content or vectors.

## CLI

With PostgreSQL migrated, `.env` configured, and the optional model dependency
installed:

```powershell
.\.venv\Scripts\python.exe -m financial_rag.cli index-folder `
  --input-directory .\local-documents `
  --label "Local demo corpus"
```

The folder command accepts only direct child files and routes them through the
same bounded upload/staging pipeline. It prints the privacy-minimized final job
JSON, not extracted text or model input.

## Database migration

Alembic head `20260812_0002` creates only the
`corpus_build_jobs` table and its created-time index. Existing revision tables
and vectors are not rewritten.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Explicit limitations

- No OCR, layout reconstruction, malware scanning, MIME/signature verification,
  encrypted PDF support, or high-fidelity table extraction.
- No resumable upload, cancellation, retry policy, queue, external worker, or
  per-stage progress events.
- No authentication, authorization, quotas, tenant isolation, or public ingress.
- No automatic orphan-staging deletion after a hard process crash.
- No persisted active-index pointer or automatic activation after restart.
- Chunk content and embeddings are intentionally stored in the local database;
  database volumes/dumps remain prohibited public artifacts.
