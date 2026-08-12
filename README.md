# financial-rag-platform

> **Status: in development.** The repository currently contains the Phase 0
> project foundation, a local Phase 1 ingestion/chunking library, a Phase 2
> offline retrieval layer, a Phase 3 PostgreSQL/pgvector persistence layer, a
> Phase 4 FastAPI adapter, Phase 5 local composition plus citation-validated
> grounded generation, a Phase 6 Streamlit client, and the Phase 7A/7B paired
> evaluation core/API/UI, Phase 8 local container/CI release gates, and a Phase 9
> bounded local document/corpus lifecycle. It also
> preserves the immutable thesis notebooks. It does not contain a populated
> database, a real corpus index, generated-answer artifacts, or published
> benchmark results.

Phase 10 adds a release-candidate **validation contract**, not a production or
public-release claim. The complete local workflow is exercised offline with
synthetic input and deterministic fake providers. PostgreSQL/pgvector,
model-enabled, Compose, dependency-audit, and hosted CI evidence remain separate
gates and must not be inferred from that synthetic test.

Phase 11 adds a loopback-only real-service acceptance runner, a cleared
synthetic filing, notebook hash/reference and exact-commit repository gates,
plus recruiter-demo and draft-release documentation. The local synthetic
Docker/PostgreSQL/BGE/OpenAI acceptance has passed, but this remains an
in-development project until its exact-commit CI and publication gates pass.

Phase 12 hardens the CPU-only container path, dependency-layer caching, archive
publication boundary, test isolation from a developer `.env`, and first public
Git baseline. It does not add benchmark, deployment, scaling, or production
claims.

`financial-rag-platform` is being developed as a local, single-user financial
document intelligence demo. The intended product will let a user ingest
financial documents, ask grounded questions with citations, inspect retrieved
chunks and their scores, compare retrieval modes, and run FinanceBench-like
evaluations.

The project originates from thesis research on retrieval-augmented generation
for financial filings. The research compared dense retrieval, hybrid dense +
BM25 retrieval with Reciprocal Rank Fusion, and hybrid retrieval followed by a
cross-encoder reranker.

## Current scope

The approved Phase 0 through Phase 12 scope provides:

- a Python 3.12+ `src` package layout,
- repository publication and data-license policies,
- dependency groups and quality-tool configuration,
- validated document/chunk metadata and deterministic identifiers,
- local UTF-8 Markdown/text loading and local PDF text extraction with PyMuPDF,
- conservative normalization and Markdown-aware recursive chunking,
- deterministic folder ingestion and offline synthetic unit tests,
- FAISS `IndexFlatIP` dense search over validated L2-normalized vectors,
- thesis-compatible BM25, weighted Reciprocal Rank Fusion, and reranking routes,
- deterministic fake providers plus lazy optional BGE-M3 model adapters,
- local ignored artifact save/load with strict compatibility manifests,
- versioned `platform_v1` retrieval and query-expansion configuration,
- SQLAlchemy 2 async PostgreSQL mappings and explicit engine/session factories,
- pgvector persistence for 1,024-dimensional `platform_v1` embeddings,
- immutable, deterministic corpus and embedding-index revisions,
- transactional revision save/load with mapping and vector compatibility gates,
- an initial reversible Alembic migration and opt-in infrastructure test,
- a typed FastAPI application factory with explicit dependency injection,
- liveness/readiness, a versioned V1 API for all three retrieval modes, and
  read-only revision-metadata endpoints,
- a versioned OpenAPI contract, request IDs, structured request logging, and
  consistent non-sensitive error responses,
- a versioned `local_v1` composition root with ASGI lifespan ownership,
- explicit local retrieval-artifact loading and optional PostgreSQL/pgvector/
  Alembic startup verification,
- deterministic top-five context assembly with full metadata lineage,
- an official OpenAI Responses API adapter with Pydantic structured output,
- grounded-answer, abstention, usage, and validated citation contracts,
- a V1 grounded-query endpoint that retains the complete retrieval score trace,
- a recruiter-facing Streamlit client that communicates only through FastAPI,
- grounded-answer/citation panels and side-by-side three-mode retrieval comparison,
- a strict `platform_eval_dataset_v1` JSON/JSONL importer with synthetic fixtures,
- paired Dense/Hybrid/Hybrid+Reranker Hit@K and MRR evaluation,
- opt-in deterministic exact-match/token-F1 answer metrics with explicit statuses,
- privacy-minimized run manifests/reports, CLI, FastAPI endpoint, and Streamlit view,
- a basic GitHub Actions quality workflow,
- non-root multi-target API/model/demo container packaging,
- local pgvector/Alembic/FastAPI/Streamlit Compose orchestration,
- independent CI quality, pgvector integration, dependency-audit, publication,
  Compose-validation, lightweight image, and CPU model-enabled image gates,
- a conservative public-boundary scanner and weekly dependency update config,
- bounded PDF/Markdown/text upload and server-owned local staging,
- durable privacy-minimized corpus-build job states in PostgreSQL,
- end-to-end ingestion, chunking, embedding, revision persistence, and activation,
- corpus/index revision listing and process-local index selection through API/UI,
- a checked-in `platform_rc_v1` source contract and safe local preflight,
- an offline synthetic HTTP test covering upload through grounded query/evaluation,
- a loopback-only `local_acceptance_v1` runner for the real composed services,
- a public synthetic annual-filing fixture and privacy-minimized acceptance result,
- exact-commit/publication/notebook-hash release preparation gates,
- the original, unchanged notebooks retained locally under `notebooks/` and
  excluded from publication pending their separate manual review.

The chunking defaults preserve the thesis parameters: 1,500 characters, 200
characters overlap, a 200-character minimum, and the documented Markdown-aware
separator order. PDF extraction is text-only and makes no OCR claim.

The historical thesis protocol is named `research_legacy_v1`. Its existing
results have known reproducibility limitations and are not presented as
production benchmarks. A corrected retrieval protocol named `platform_v1` is
now implemented for offline controlled comparisons. The evaluation subsystem is
also implemented, but no new FinanceBench run or result is bundled or claimed.
Claim-level grounding and optional RAGAS/RAGChecker adapters remain later work.

## Planned architecture

The architecture includes Python 3.12+, explicit application services,
LangChain adapters without opaque chains, the official OpenAI integration,
Pydantic v2, PostgreSQL with pgvector, SQLAlchemy 2.0, Alembic,
Streamlit, pytest, structured logging, Docker Compose, and GitHub Actions.
Public deployment and multi-user operational controls remain roadmap items.

## Repository layout

```text
apps/                    Local Streamlit entry point
configs/                 Versioned, non-secret retrieval/runtime configuration
data/                    Local research data; contents are ignored
docs/                    Audit, policies, and phase reports
notebooks/               Immutable thesis research artifacts
scripts/                 Reserved for explicit maintenance/developer commands
src/financial_rag/       Typed domain, service, storage, and API packages
tests/                   Offline synthetic unit, API, and opt-in integration tests
```

## Local containers

With Docker Engine/Desktop and Compose v2:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The stack binds PostgreSQL, FastAPI, and Streamlit to loopback. Without an
explicit compatible ignored retrieval artifact, it provides infrastructure,
liveness, and OpenAPI behavior but retrieval/generation remain unavailable.
See [docs/container-runtime.md](docs/container-runtime.md) for artifact setup,
migrations, limitations, and cleanup.

## Foundation setup

On Windows PowerShell with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe -q
```

Install the optional local ASGI server and model adapters, configure an ignored
`.env`, and start the local composition factory with:

```powershell
py -3.12 -m pip install -e ".[api,models,dev]"
.\.venv\Scripts\uvicorn.exe financial_rag.runtime.app:create_local_app --factory --host 127.0.0.1 --port 8000
```

With no local artifact path, this factory supports liveness and OpenAPI but
returns `503` for retrieval/generation. It never discovers an index or connects
to PostgreSQL implicitly. Generation additionally requires `OPENAI_API_KEY`.
See [docs/local-runtime.md](docs/local-runtime.md).

The `api` extra installs Uvicorn and `demo` installs Streamlit/HTTPX. The
evaluation core has no extra runtime dependency; the empty `evaluation` extra
is retained as a stable install target for future optional evaluators. The
optional `models` extra installs FlagEmbedding for explicit local/cloud BGE-M3
execution; it is not installed by `.[dev]` and automated tests use deterministic
fake providers. The Docker `api-models` target is the verified CPU-only
recruiter-demo path and installs pinned Torch from the official PyTorch CPU
wheel index.

## Environment variables

Copy `.env.example` to the ignored `.env` for local runtime configuration.
Never commit `.env`, database credentials, or connection strings. No automated
test is allowed to call the live OpenAI API. The key is optional: without it,
retrieval remains usable but grounded generation returns HTTP 503. See
[docs/storage-design.md](docs/storage-design.md) for migration commands and
[docs/grounded-generation.md](docs/grounded-generation.md) for generation limits.
`API_DOCS_ENABLED` controls only the local OpenAPI and Swagger UI routes.
`FINANCIAL_RAG_API_URL` configures only the Streamlit-to-FastAPI connection; the
UI never receives `OPENAI_API_KEY`.

Phase 9 upload/indexing additionally requires PostgreSQL at Alembic head
`20260812_0002` and the optional `models` extra. Upload staging defaults to the
ignored `uploads/` directory and is removed after each completed/failed job.

## Data and notebooks

Source PDFs, extracted/cleaned text, embeddings, FAISS indexes, generated
contexts, local databases, model caches, and local evaluation runs must remain
outside the public commit set. See [DATA_LICENSE.md](DATA_LICENSE.md) and
[docs/publication-policy.md](docs/publication-policy.md).

The 15 thesis notebooks are preserved byte-for-byte and are not runtime
dependencies. Their code and saved outputs represent `research_legacy_v1` and
may contain historical paths or third-party excerpts. See
[notebooks/README.md](notebooks/README.md) before publishing them.

## Project documentation

- [Notebook migration audit](docs/notebook-migration-audit.md)
- [Publication policy](docs/publication-policy.md)
- [Phase 0 report](docs/phase-0-report.md)
- [Phase 1 data pipeline](docs/data-pipeline.md)
- [Phase 1 report](docs/phase-1-report.md)
- [Retrieval design](docs/retrieval-design.md)
- [Cloud indexing](docs/cloud-indexing.md)
- [Phase 2 report](docs/phase-2-report.md)
- [Storage and revision design](docs/storage-design.md)
- [Phase 3 report](docs/phase-3-report.md)
- [FastAPI design](docs/api-design.md)
- [Phase 4 report](docs/phase-4-report.md)
- [Local runtime composition](docs/local-runtime.md)
- [Grounded generation and citations](docs/grounded-generation.md)
- [Phase 5 report](docs/phase-5-report.md)
- [Local Streamlit demo](docs/streamlit-demo.md)
- [Phase 6 report](docs/phase-6-report.md)
- [`platform_eval_v1` evaluation](docs/evaluation.md)
- [Phase 7 report](docs/phase-7-report.md)
- [Architecture and trust boundaries](docs/architecture.md)
- [Local container runtime](docs/container-runtime.md)
- [Public release checklist](docs/release-checklist.md)
- [Phase 8 report](docs/phase-8-report.md)
- [Local corpus and index lifecycle](docs/corpus-lifecycle.md)
- [Phase 9 report](docs/phase-9-report.md)
- [Release-candidate validation](docs/release-candidate.md)
- [Phase 10 report](docs/phase-10-report.md)
- [Real local acceptance](docs/local-acceptance.md)
- [Recruiter demo walkthrough](docs/recruiter-demo.md)
- [Draft v0.1.0 release notes](docs/release-notes-v0.1.0-draft.md)
- [Phase 11 report](docs/phase-11-report.md)
- [Phase 12 report](docs/phase-12-report.md)

## Limitations

This is currently a development foundation, not a deployed or production-ready
system. Authentication, public hosting, multi-user isolation, distributed
retrieval, managed storage, scaling, and operational service-level guarantees
are future work.

Document upload and corpus selection are implemented only for the bounded local
single-user demo. Jobs run in-process and are not resumable or suitable for
public/multi-user ingress.

## Licenses

Original project code is licensed under the [MIT License](LICENSE). FinanceBench
and third-party documents are governed separately; see
[DATA_LICENSE.md](DATA_LICENSE.md).
