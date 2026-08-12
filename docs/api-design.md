# FastAPI API design

## API foundation and document lifecycle

The API is a thin HTTP adapter over the tested retrieval service and
revision reader. It deliberately does not add hidden retrieval chains,
OpenAI calls, document upload, background jobs, evaluation, Docker, Streamlit,
authentication, or public deployment.

The grounded-query extension retains every retrieval and revision contract and adds one
grounded-query route over the tested generation orchestration. The standalone
retrieval route remains available for controlled mode comparisons.

The document lifecycle adds bounded local multipart upload, durable privacy-minimized build
status, revision listing, and explicit active-index selection. It does not turn
the API into a public or multi-user service.

## Routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health/live` | Confirms that the ASGI process responds. |
| `GET` | `/health/ready` | Reports whether retrieval and revision capabilities were injected. |
| `POST` | `/api/v1/query` | Returns a grounded answer, validated citations, contexts, and retrieval trace. |
| `POST` | `/api/v1/retrieval/query` | Runs `dense`, `hybrid`, or `hybrid_reranked`. |
| `POST` | `/api/v1/evaluations/retrieval` | Runs a bounded synchronous paired evaluation. |
| `GET` | `/api/v1/corpora/{corpus_revision_id}` | Returns corpus fingerprints and counts only. |
| `GET` | `/api/v1/indexes/{index_revision_id}` | Returns index compatibility metadata only. |
| `POST` | `/api/v1/corpus-jobs` | Accepts a bounded local document batch and returns HTTP 202. |
| `GET` | `/api/v1/corpus-jobs` | Lists recent privacy-minimized build states. |
| `GET` | `/api/v1/corpus-jobs/{job_id}` | Returns one build state without source content. |
| `GET` | `/api/v1/corpora` | Lists recent corpus revision metadata. |
| `GET` | `/api/v1/indexes` | Lists recent index revision metadata. |
| `POST` | `/api/v1/indexes/{index_revision_id}/activate` | Selects a compatible persisted index. |

The retrieval response remains the existing `RetrievalResult`. It preserves query
expansion, retrieval mode, configuration fingerprint, complete document/page/
section lineage, and dense/BM25/RRF/reranker score fields. The grounded route
also embeds this complete response while exposing the exact bounded contexts.

Example request:

```json
{
  "query": "What were the capital expenditures?",
  "mode": "hybrid"
}
```

`mode` defaults to `hybrid`. Queries are stripped, must contain at least one
character, and are limited to 4,096 characters. Unknown fields and invalid enum
values return HTTP 422.

## Dependency injection and blocking work

`create_app()` accepts an explicit `ApiContainer` with structural ports for:

- synchronous `RetrievalUseCase.retrieve()`;
- synchronous `GroundedGenerationUseCase.answer()`;
- synchronous `EvaluationUseCase.evaluate()`;
- asynchronous metadata-only `RevisionReader` methods.
- asynchronous bounded `CorpusIndexingUseCase` methods.

The routes never construct a model, index, engine, or database session.
Synchronous retrieval is run in Starlette's thread pool so model or FAISS work
does not block the event loop. The persistence store implements the revision-reader
port without loading chunk text or embedding vectors for metadata endpoints.

Calling `create_app()` without a container is safe and useful for OpenAPI and
liveness checks. Query/revision endpoints then fail with HTTP 503. This explicit
composition boundary prevents import-time network calls, hidden model downloads,
and accidental database connections. `create_local_app()` owns the
concrete local services through ASGI lifespan without changing route contracts.

## Health semantics

`/health/live` only confirms process responsiveness.

`/health/ready` is intentionally a configured-capability check, not a database,
model, GPU, or network probe. Retrieval is the required query capability:

- HTTP 200 when a retrieval service is injected;
- HTTP 503 otherwise.

The response separately reports generation, evaluation, revision-reader, and
indexing availability.
It does not make availability or service-level claims about external infrastructure.

The evaluation request accepts at most 500 validated query items. Its response
contains IDs, fingerprints, statuses, and metrics, but not query, reference-
answer, generated-answer, or source-chunk text. The evaluation layer has no durable
job store, so the POST response is the complete synchronous run result.

## Errors and request correlation

Expected errors use one envelope:

```json
{
  "error": {
    "code": "request_validation_failed",
    "message": "The request did not match the API contract.",
    "request_id": "8ed51df23ab64ead8949a20f965e4615",
    "details": []
  }
}
```

Mappings are explicit:

- 400 for ordinary domain rejection;
- 404 for a missing revision;
- 404 for a missing build job;
- 409 for revision conflicts/incompatibility;
- 409 for an invalid/concurrent build-job transition;
- 422 for HTTP/Pydantic validation;
- 502 for provider output that failed safe generation/citation validation.
- 503 for an uninjected or unavailable local dependency;
- 500 for an unexpected error with a generic response.

Validation details include only field location, message, and error type; they do
not echo submitted inputs. Provider/internal exception details are not exposed.
Every response carries `X-Request-ID`. A supplied ID is accepted only when it is
1–64 characters from `[A-Za-z0-9._-]`; otherwise a new ID is generated.

Structured request logs contain request ID, method, route template, status, and duration.
They omit query strings, request/response bodies, chunk content, headers,
credentials, and database URLs.

## OpenAPI and local inspection

FastAPI generates `/openapi.json` and `/docs` when `API_DOCS_ENABLED=true`.
Request examples, result schemas, and the error envelope are included. Set the
flag to `false` to disable both routes.

Install the optional ASGI server and inspect the safe unconfigured factory:

```powershell
py -3.12 -m pip install -e ".[api,dev]"
.\.venv\Scripts\uvicorn.exe financial_rag.api.app:create_app --factory --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/openapi.json | Out-Null
```

The default `/health/ready` and retrieval routes return 503 because no corpus or
model is silently selected. Automated API tests instead inject the real
`RetrievalService` with deterministic fake embedding/reranking providers and a
synthetic revision reader.

## Security and publication limitations

This remains a local, single-user development API. It has no authentication,
authorization, TLS termination, rate limiting, malware scanning, tenant
isolation, CORS policy, proxy trust configuration, or public deployment review.
Do not bind it to a public interface or expose it to untrusted clients.

Retrieval responses contain chunk text from the configured local corpus. Source
PDFs, parsed text, chunks, vectors, database files/dumps, `.env`, and model
caches remain prohibited public repository artifacts. Request/response captures
from real financial documents must not be committed or published.
