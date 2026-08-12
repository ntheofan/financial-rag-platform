# Recruiter demo walkthrough

## Intended presentation

Use only the checked synthetic ACME filing. The demo should take about five
minutes and should be described as an in-development local single-user
financial-document intelligence platform.

## Before the call

1. Complete `docs/local-acceptance.md` successfully.
2. Open `http://127.0.0.1:8501` and confirm the five tabs render.
3. Confirm no real filing, FinanceBench row, prior local job, or restricted
   screenshot is visible.
4. Keep `.env`, terminals containing credentials, Docker logs, and database
   tools off screen.

## Walkthrough

1. **Documents:** upload `tests/fixtures/demo/acme-2025-10k.md`, wait for the
   completed privacy-minimized job, refresh until its visible status is
   `completed`, and activate its index revision.
2. **Ask:** ask “What were ACME's capital expenditures and operating cash
   flow?” Show the grounded answer, citations, source filename, section, and
   retrieval score trace.
3. **Compare retrieval:** run the identical query across Dense, Hybrid, and
   Hybrid + Reranker. Explain that the comparison preserves `platform_v1`
   parameters and exposes component scores.
4. **Evaluate:** upload `tests/fixtures/demo/acme-benchmark.json`. Leave answer
   metrics disabled for the fast retrieval-only walkthrough. Explain Hit@K/MRR
   and the paired mode comparison without claiming a FinanceBench result.
5. **Current scope:** close with the explicit local-demo limitations and future
   work.

## Accurate claims

- “The application has modular, tested ingestion, retrieval, generation,
  evaluation, persistence, API, and demo boundaries.”
- “Automated tests use synthetic data and fake providers; live OpenAI is never
  called by tests.”
- “Real local acceptance is recorded separately from offline test evidence.”
- “No source filings, embeddings, indexes, contexts, database data, or secrets
  are published.”

Do not claim production deployment, benchmark superiority, complete PDF/table
fidelity, financial correctness, multi-user security, or operational scale.

The benchmark's relevance IDs are contract-tested against chunks rebuilt from
the checked synthetic Markdown fixture. They are not FinanceBench identifiers
or results.
