# Changelog

Notable changes to the public portfolio project are recorded here. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses semantic versioning for public release tags.

## [0.1.0] - 2026-08-12

### Added

- Recruiter-facing `v0.1.0` release notes.
- A checked synthetic benchmark aligned with the public ACME demo document.
- Hosted CI contracts for portable pytest temporary files and explicit Buildx
  setup.

### Changed

- The document view refreshes the visible submitted-job status from the latest
  backend result.
- Recruiter and README guidance now describe the exact synthetic demo inputs
  and current verification evidence.

### Security

- Publication gates exclude secrets, real filings, FinanceBench
  artifacts, derived corpora, indexes, databases, contexts, and model caches.
