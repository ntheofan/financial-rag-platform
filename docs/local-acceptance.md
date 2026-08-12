# Real local acceptance

## Boundary

This acceptance sequence is for the local single-user demo. It uses the
checked-in original synthetic filing at
`tests/fixtures/demo/acme-2025-10k.md`. It must not be replaced with a source
filing, FinanceBench document, or uncleared local content.

The runner accepts only an HTTP loopback API URL. It never reads `.env`, starts
containers, connects directly to PostgreSQL, or receives provider credentials.
Those responsibilities remain in the existing composition root and Compose
configuration.

## Prerequisites

- Python 3.12 and `.[demo,models,dev,security]` installed;
- Docker Engine/Desktop with Compose v2;
- enough local storage for the BGE-M3 and reranker weights in the ignored model
  volume;
- an ignored `.env` with `OPENAI_API_KEY` set for the real grounded-generation
  step;
- loopback ports 5432, 8000, and 8501 available, or local overrides in `.env`.

Never paste `.env` contents into an issue, report, screenshot, or terminal log.

## Sequence

```powershell
Copy-Item .env.example .env
# Edit .env locally; set OPENAI_API_KEY and keep the file ignored.
docker compose config --quiet
docker compose up --build --wait
docker compose ps
.\.venv\Scripts\python.exe scripts/run_local_acceptance.py
docker compose down
```

The first model-enabled startup/build may download substantial model weights.
The cache remains in the ignored Docker volume. Do not publish that volume or
its build/runtime logs without review.

The `models` extra constrains `sentence-transformers` to the tested 2.x adapter
family because newer eager package imports pull training/dataset modules into
ordinary API startup. This is an import-isolation compatibility bound, not a
model-quality claim.

## What a pass proves

One successful `local_acceptance_result_v1` confirms, for the named local
environment:

- PostgreSQL/pgvector-backed upload job and immutable revision persistence;
- real BGE-M3 embedding and configured reranker execution;
- activation into all three retrieval modes;
- a non-abstained grounded answer with validated citation lineage;
- a complete paired `platform_eval_v1` retrieval run;
- FastAPI composition across all required capabilities.

The result emits only status, opaque revision/job IDs, chunk counts, citation
count, and completed mode names. It emits no document text, answer, context,
prompt, vector, database URL, API key, or local path.

## What it does not prove

It is not a benchmark, load test, security assessment, public-deployment test,
quality claim for real filings, or operational service-level guarantee. It does
not validate OCR, multi-user use, authentication, scaling, or managed storage.
