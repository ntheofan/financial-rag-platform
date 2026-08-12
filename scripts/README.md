# Scripts

Reusable command logic lives in the typed package rather than ad-hoc scripts.
The Phase 7 retrieval evaluation command is available as:

```powershell
.\.venv\Scripts\python.exe -m financial_rag.cli evaluate-retrieval --help
```

This directory remains available for narrowly scoped maintenance wrappers.

`check_publication.py` inspects Git-tracked and non-ignored untracked files for
restricted paths, artifact types, large files, credential patterns, and local
home paths. It logs filenames and safe reason labels only; it never prints
candidate content.

Run it before staging or publishing:

```powershell
.\.venv\Scripts\python.exe scripts/check_publication.py
```

This is a conservative automated gate, not a replacement for the manual review
in [`docs/publication-policy.md`](../docs/publication-policy.md).

`check_release_candidate.py` validates the checked-in `platform_rc_v1` source
contract and reports local infrastructure prerequisites without connecting to
them or printing environment values:

```powershell
.\.venv\Scripts\python.exe scripts/check_release_candidate.py
.\.venv\Scripts\python.exe scripts/check_release_candidate.py --require-infrastructure
```

The default command fails on source-contract drift. The strict form also fails
when Docker, a database URL, or the optional model adapter is unavailable; it
still does not run PostgreSQL, model, Compose, or OpenAI smoke tests by itself.

With the real local Compose stack already running, the Phase 11 acceptance
runner uploads only the checked synthetic fixture to a loopback API and prints
a privacy-minimized result:

```powershell
.\.venv\Scripts\python.exe scripts/run_local_acceptance.py
```

It requires indexing, revisions, retrieval, generation, and evaluation to be
ready. Non-loopback URLs, URL credentials, arbitrary fixture paths, failed
retrieval modes, abstention, missing citations, and incomplete evaluation all
fail closed.

Before an exact-commit release review, run:

```powershell
.\.venv\Scripts\python.exe scripts/check_release_repository.py
```

This reports only state/counts. It requires a resolvable `HEAD`, no public
untracked/staged/unstaged changes, a clean publication scan, and equality with
the notebook hash snapshot. It does not stage, commit, push, or tag anything.
