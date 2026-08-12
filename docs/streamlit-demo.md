# Local Streamlit demo

## Phase 6 foundation and Phase 9 lifecycle

The Streamlit application is a thin local client for the existing FastAPI
contracts. It does not import or connect directly to PostgreSQL, FAISS,
FlagEmbedding, or OpenAI. It receives no model-provider key and keeps no durable
copy of queries, answers, contexts, or document text.

The `Documents` tab now uses the Phase 9 FastAPI lifecycle for bounded local
upload, build-job status, revision listing, and active-index selection. It does
not read or write staging/database/model state directly.

## Demo features

The `Ask` tab provides:

- a bounded question field;
- a `dense`, `hybrid`, or `hybrid + reranker` selector;
- grounded answer or explicit abstention;
- expandable `C1`–`C5` citation panels with file, page, section, chunk ID, and
  exact context exposed to generation;
- expandable retrieved chunks with rank and every score family actually
  returned by the selected mode;
- model identifier and provider token usage when available.

The `Compare retrieval` tab sends the identical normalized query to all three
retrieval modes. Results are shown side by side in controlled mode order. A
failure in one mode remains visible while successful modes are preserved. The
view also reports Jaccard overlap between returned chunk-ID sets; this is a
display diagnostic, not a retrieval-quality metric.

The `Evaluate` tab accepts an in-memory `platform_eval_dataset_v1` JSON/JSONL
file, Hit@K cutoffs, and an optional answer-metrics switch. It calls the bounded
FastAPI evaluation endpoint and displays aggregate and per-query status tables.
Skipped/failed metrics remain blank rather than appearing as zero.

The sidebar provides an explicit readiness check. It does not poll the backend
or make a network call merely because the module was imported.

The `Documents` tab accepts up to 10 `.pdf`, `.md`, or `.txt` files subject to
the backend's 20 MiB per-file and 50 MiB total limits. Refresh is manual; the UI
does not claim streaming progress. Ready persisted indexes can be activated for
subsequent Ask/Compare/Evaluate requests.

## Local commands

Install the API, model, demo, and development extras:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[api,models,demo,dev]"
Copy-Item .env.example .env
```

Configure only the ignored `.env`. Existing artifacts may still be supplied
with `RETRIEVAL_ARTIFACT_DIRECTORY`. Phase 9 upload/indexing instead requires
`DATABASE_ENABLED=true`, a migrated database, and the optional model extra. Set
`OPENAI_API_KEY` only when grounded answers should be available. The Streamlit
client uses only:

```dotenv
FINANCIAL_RAG_API_URL=http://127.0.0.1:8000
DEMO_REQUEST_TIMEOUT_SECONDS=90
```

Start the backend in one PowerShell terminal:

```powershell
.\.venv\Scripts\uvicorn.exe financial_rag.runtime.app:create_local_app --factory --host 127.0.0.1 --port 8000
```

Start the UI in a second terminal:

```powershell
.\.venv\Scripts\streamlit.exe run apps\streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501`. Keep both processes bound to loopback. Upload
validation is bounded but the project has no authentication, TLS termination,
rate limiting, malware scanning, tenant isolation, or public deployment review.

## Testing and data handling

The typed HTTP client is tested with `httpx.MockTransport` and synthetic
Pydantic responses. Tests cover readiness, grounded answers, identical paired
queries, partial failures, unreachable APIs, malformed responses, URL
validation, score display, and result overlap. They make no live API, model, or
database request.

The UI may display restricted local chunk text returned by FastAPI. Do not save
screenshots, browser exports, logs, or response captures from a real corpus in
the public repository. Public screenshots require synthetic or separately
cleared content under the publication policy.
