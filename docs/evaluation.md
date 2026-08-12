# `platform_eval_v1` evaluation

## Protocol boundary

`platform_eval_v1` is the corrected application evaluation protocol. It remains
separate from `research_legacy_v1`, the historical thesis results with their
documented reproducibility limitations. New runs never overwrite or relabel
historical outputs.

The subsystem evaluates small FinanceBench-like datasets whose evidence has
already been mapped to immutable platform chunk IDs. It does not bundle
FinanceBench questions, answers, filings, evidence pages, parsed text, or
derived indexes. The checked-in fixture is entirely synthetic.

## Benchmark contract

JSON object form:

```json
{
  "schema_version": "platform_eval_dataset_v1",
  "dataset_id": "local-cleared-v1",
  "items": [
    {
      "query_id": "q-001",
      "query": "What were capital expenditures?",
      "relevant_chunk_ids": ["chunk_..."],
      "expected_answer": "Optional reference answer"
    }
  ]
}
```

JSONL contains one item object per line; `dataset_id` defaults to the filename
stem or an explicit CLI override. Query IDs must be unique. Relevance is
strictly membership in `relevant_chunk_ids`; document-level or fuzzy matching
is not silently substituted.

Import is limited to UTF-8 `.json`/`.jsonl`, 5 MiB, and 500 items. The schema
rejects blank/duplicate relevance IDs, oversized fields, duplicate query IDs,
unknown fields, unsupported extensions, and malformed content.

## Paired retrieval metrics

Every configured mode receives the same validated query-ID set:

- `dense`;
- `hybrid`;
- `hybrid_reranked`.

Canonical retrieval metrics are binary Hit@K, first relevant rank, reciprocal
rank, and MRR. A successful retrieval miss has numeric zero. A retrieval failure
has status `failed`, null metrics, an explicit failure count, and is excluded
from the metric denominator. Failure is never encoded as a zero.

## Deterministic answer metrics

Answer metrics are opt-in and require `expected_answer` plus configured grounded
generation. Normalized exact match and bag-of-token F1 case-fold text and compare
Unicode word tokens. They are transparent baselines, not evidence of financial
correctness, numeric equivalence, semantic entailment, or citation quality.

When answer metrics are not requested, a reference is missing, or generation is
unavailable, status is `skipped` and metrics are null. Provider/domain failures
produce `failed` and null metrics. RAGAS/RAGChecker are not part of this implementation.

## Provenance and report privacy

Reports record run ID/time, protocol, dataset/config/corpus fingerprints, the
complete query/mode status matrix, aggregate denominators, metrics, and retrieved
chunk IDs. They omit question text, reference answers, generated answers, source
filenames, and chunk content.

Exported reports still reveal local IDs and metrics, so they belong under the
ignored `evaluation-runs/` directory until manually reviewed for publication.

## CLI

Run the default checked-in evaluation config against an explicit compatible
local index:

```powershell
.\.venv\Scripts\python.exe -m financial_rag.cli evaluate-retrieval `
  --benchmark C:\path\to\local-benchmark.jsonl `
  --artifact-directory C:\path\to\ignored-index `
  --evaluation-config configs\evaluation\platform_eval_v1.json `
  --output evaluation-runs\platform-eval-report.json
```

Without `--output`, a manifest/aggregate summary is printed. Existing reports
are not overwritten unless `--overwrite` is supplied. The CLI may make local
model/provider calls according to runtime configuration; tests do not.

## FastAPI and Streamlit

`POST /api/v1/evaluations/retrieval` accepts one validated dataset and config,
then synchronously returns a bounded report. It is not a durable job API: there
is no run database, background worker, cancellation, or GET-by-ID contract.

The Streamlit `Evaluate` tab accepts JSON/JSONL in memory, lets the operator
select Hit@K cutoffs and optional answer metrics, calls FastAPI, and displays
aggregate/per-query status tables. It does not persist uploads or communicate
directly with retrieval, generation, or storage services.
