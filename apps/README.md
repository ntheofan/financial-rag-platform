# Applications

`streamlit_app.py` is the local portfolio demo. It communicates only
with the configured FastAPI base URL and never imports storage, retrieval model,
or OpenAI adapters.

The `Documents` tab uses only FastAPI for bounded local upload, durable
job status, revision listing, and index activation. It never imports staging,
storage, retrieval-model, or provider adapters.

The `Evaluate` tab accepts a small local benchmark in memory and displays the
paired `platform_eval_v1` report returned by FastAPI. The checked local demo
uses `tests/fixtures/demo/acme-benchmark.json`, whose relevance IDs
are tested against the matching synthetic document. The UI does not persist
the benchmark or evaluation output.

Refreshing document jobs also replaces the submitted-job snapshot with the
latest matching backend state, so a completed build is not left visibly marked
as pending.
