# Thesis notebooks — `research_legacy_v1`

The 15 Jupyter notebooks in this directory are the original thesis research
artifacts. They are not application code and are not runtime dependencies of
`financial-rag-platform`.

## Immutability rule

The notebook files must remain byte-for-byte unchanged. Do not:

- edit source or Markdown cells,
- clear, add, or rerun outputs,
- normalize metadata or line endings,
- run formatters or notebook cleaners against them,
- rename, move, or delete them.

`.gitattributes` marks `*.ipynb` as binary so Git does not normalize their
contents. Ruff and mypy exclude this directory.

## Reproducibility status

The notebooks and their stored outputs are classified as
`research_legacy_v1`. The migration audit documents known differences between
current notebook source and historical generated artifacts. Do not present
their metrics as a reproducible production benchmark.

The corrected future protocol will be named `platform_v1` and implemented in
the typed application package rather than by changing these notebooks.

## Data and publication warning

Notebook execution depends on local files under `data/`, which are intentionally
ignored. Some saved outputs contain historical absolute paths, FinanceBench
answers, or third-party document excerpts. A separate manual publication review
and explicit approval are required before the notebooks may be included in a
public commit.

See:

- [Migration audit](../docs/notebook-migration-audit.md)
- [Publication policy](../docs/publication-policy.md)
- [Data licensing](../DATA_LICENSE.md)
