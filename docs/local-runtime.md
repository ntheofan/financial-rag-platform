# Local runtime composition

## Scope

Phase 5 introduces the explicit composition root for the local, single-user
demo. It joins the already tested retrieval, persistence, generation, and HTTP
adapters without discovering a corpus, loading a model, connecting to a
database, or making a network request at module import time.

`configs/runtime/local_v1.json` is the non-secret runtime contract. Machine
paths, credentials, and opt-in switches remain in the ignored `.env` and are
validated by `LocalRuntimeSettings`. The recruiter-demo configuration runs
both BGE adapters explicitly on CPU with inference batch size `1`; this favors
predictable local memory use over throughput and does not change retrieval
models or scoring semantics.

## Startup and shutdown

`financial_rag.runtime.app:create_local_app` is the Uvicorn factory. Its ASGI
lifespan:

1. validates `local_v1` and `platform_v1` configuration;
2. loads retrieval artifacts only when `RETRIEVAL_ARTIFACT_DIRECTORY` is set;
3. creates lazy BGE-M3 adapters without downloading or loading weights;
4. creates a SQLAlchemy async engine and revision reader only when
   `DATABASE_ENABLED=true`;
5. optionally verifies PostgreSQL connectivity, the `vector` extension, and
   Alembic head `20260812_0002` when `DATABASE_SMOKE_ON_STARTUP=true`;
6. configures grounded generation only when both retrieval and
   `OPENAI_API_KEY` are available;
7. disposes the owned SQLAlchemy engine on shutdown.

Explicitly configured but missing/incompatible artifacts fail startup. An
unset artifact path is different: the application can expose liveness and
OpenAPI, while retrieval and generation endpoints return HTTP 503.

## Local configuration

Copy `.env.example` to `.env` and set only the components you intend to use.
For retrieval, point `RETRIEVAL_ARTIFACT_DIRECTORY` to an ignored Phase 2
artifact directory whose manifest matches `platform_v1` and the Phase 1
chunking fingerprint. Do not place local paths in checked-in JSON.

Database startup probes are opt-in because they open a real local connection.
`DATABASE_URL` must use `postgresql+asyncpg://`. The smoke probe is a diagnostic,
not a continuous health check or availability guarantee.

Install all local runtime extras and start the factory:

```powershell
py -3.12 -m pip install -e ".[api,models,dev]"
.\.venv\Scripts\uvicorn.exe financial_rag.runtime.app:create_local_app --factory --host 127.0.0.1 --port 8000
```

With `DATABASE_ENABLED=true`, startup also recovers interrupted Phase 9 jobs and
composes bounded upload/indexing services using `UPLOAD_STAGING_DIRECTORY`.
Keep the server bound to localhost. This runtime has no authentication, public
deployment controls, resumable worker, or managed infrastructure.
