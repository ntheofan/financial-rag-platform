# Applications

`streamlit_app.py` is the Phase 6 local recruiter demo. It communicates only
with the configured FastAPI base URL and never imports storage, retrieval model,
or OpenAI adapters.

The Phase 9 `Documents` tab uses only FastAPI for bounded local upload, durable
job status, revision listing, and index activation. It never imports staging,
storage, retrieval-model, or provider adapters.

The `Evaluate` tab accepts a small local benchmark in memory and displays the
paired `platform_eval_v1` report returned by FastAPI. It does not persist the
benchmark or evaluation output.
