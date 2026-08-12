# Configuration

This directory contains versioned, non-secret protocol configuration.

Planned protocol names:

- `research_legacy_v1`: immutable description of the historical thesis runs,
- `platform_v1`: corrected, reproducible comparison protocol.

`retrieval/platform_v1.json` is the active retrieval contract. It
records the embedding/index semantics, BM25 and weighted-RRF parameters,
candidate counts, reranker identifier, and versioned finance alias rules. A
fingerprint of the complete validated configuration is written to every local
index manifest.

`runtime/local_v1.json` composes that retrieval contract with the unchanged
ingestion chunking parameters, lazy local model settings, and the bounded top-five
generation-context policy. It contains no machine-specific path or secret.

`evaluation/platform_eval_v1.json` defines the corrected paired evaluation
mode order, Hit@K cutoffs, and answer-metric switch. Its fingerprint is recorded
in every new evaluation manifest.

`release/platform_rc_v1.json` freezes the release source-validation contract:
development status, package/protocol versions, migration head, OpenAPI paths,
notebook inventory count, and the source/infrastructure gate names. It contains
no test result, machine state, secret, corpus content, or release decision.

`release/local_acceptance_v1.json` defines the real-service smoke:
loopback API URL, checked synthetic fixture, synthetic question, and bounded
request/job polling timeouts. Notebook integrity is checked locally against an
ignored private snapshot; neither notebook filenames nor hashes are published.

Secrets and machine-specific paths must never be stored here.
