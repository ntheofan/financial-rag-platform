# Public repository publication policy

This policy defines the public boundary for `financial-rag-platform`. It applies
to local development, staging, commits, pull requests, CI artifacts, releases,
screenshots, and demonstrations.

## Allowed content

The public repository may contain:

- original project source code and documentation licensed under MIT,
- non-secret configuration templates such as `.env.example`,
- dependency and quality-tool configuration,
- synthetic test fixtures created specifically for this project,
- tiny third-party fixtures only when their license and attribution have been
  reviewed and documented,
- aggregate results that contain no restricted source text, generated context,
  personal path, credential, or unpublished data,
- screenshots produced only from synthetic or separately cleared documents.

## Prohibited content

The following must never be committed, pushed, attached to a release, uploaded
as a CI artifact, or shown in a public demo unless a later written policy change
explicitly clears it:

- `.env` files or real credentials, tokens, connection strings, private keys,
  cookies, session data, or secret-bearing logs,
- source financial PDFs,
- Docling parsed JSON, extracted Markdown, cleaned full text, page images, or
  OCR output,
- chunk corpora, generated contexts, generated-answer context dumps, or raw
  evaluation examples containing source text,
- embeddings, NumPy matrices, FAISS/vector indexes, pickle files, or model
  checkpoints,
- PostgreSQL files, SQLite databases, Docker volumes, database dumps, uploads,
  job payloads, or local runtime state,
- Hugging Face, sentence-transformer, Docling, OpenAI, or other model caches,
- local absolute paths, usernames, machine identifiers, or private repository
  locations in newly generated public artifacts,
- benchmark data or model outputs whose license or publication status has not
  been verified,
- generated archives such as ZIP, TAR, or 7z bundles, unless a later explicit
  allowlist and manual content review approves a specific release artifact.

These rules apply even when a file is small enough for Git or Git LFS.

## FinanceBench boundary

FinanceBench is governed separately from this project's MIT-licensed code. The
dataset card identifies CC BY-NC 4.0 terms. The public repository will not
bundle FinanceBench rows, source PDFs, evidence pages, parsed filings, or
derived vector/search artifacts. Future tooling may download or import data
from official sources into ignored local directories.

See [../DATA_LICENSE.md](../DATA_LICENSE.md) for attribution and limitations.

## Thesis notebooks

The 15 notebooks under `notebooks/` are immutable `research_legacy_v1`
artifacts. They must remain byte-for-byte unchanged. Some saved outputs contain
historical paths, benchmark answers, or excerpts of third-party documents.

Their presence in the working tree does not automatically authorize public
publication. Before they are staged, all 15 files require a separate manual
publication review and explicit approval. If that review is not complete, the
notebooks remain local research artifacts even though the surrounding project
foundation may be published.

## Required pre-publication review

Before any public commit or pull request:

1. Inspect tracked, untracked, and ignored files.
2. Confirm that `.env` and local data are ignored.
3. Inspect the complete staged filename list and staged diff.
4. Scan staged text for credentials and absolute local paths.
5. Check for large binary files and archives.
6. Verify third-party attribution and license notes.
7. Confirm that no notebook changed; if notebooks are staged, complete the
   separate notebook publication review first.

Useful PowerShell commands:

```powershell
git status --short --ignored
git diff --cached --name-only
git diff --cached --check
git check-ignore -v .env data\raw\financebench_open_source.jsonl
rg -n --hidden -g '!.git/**' 'OPENAI_API_KEY|sk-[A-Za-z0-9_-]{16,}' .
Get-ChildItem -Recurse -File | Where-Object Length -GT 10MB
Get-ChildItem notebooks\*.ipynb | Get-FileHash -Algorithm SHA256
```

Phase 8 adds a conservative automated first pass:

```powershell
.\.venv\Scripts\python.exe scripts/check_publication.py
```

The scanner checks all tracked and non-ignored untracked candidates. It rejects
restricted directories and artifact types, unreviewed notebooks, files over 10
MiB, common credential patterns, and local home paths. It prints no candidate
content. CI and the pre-push/manual pre-commit stage run this command, but it
does not replace staged-diff, notebook-hash, license, screenshot, log, or claim
review.

Do not stage files merely to test whether ignore rules work. Use
`git check-ignore -v` first.

## Operational scope

The first release target is a local, single-user recruiter demo. This policy
does not approve public deployment. Authentication, authorization, quotas,
managed storage, tenant isolation, retention controls, and operational scaling
remain future work.
