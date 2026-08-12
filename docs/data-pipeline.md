# Phase 1 data pipeline

## Scope

Phase 1 implements an offline, local pipeline:

```text
local .md/.txt/.pdf
        |
        v
format validation and byte hashing
        |
        v
UTF-8 decoding or page-level PyMuPDF text extraction
        |
        v
conservative text normalization
        |
        v
LangChain Document objects with validated source metadata
        |
        v
Markdown-aware recursive splitting
        |
        v
LangChain Document chunks with complete metadata lineage
```

The phase ends at in-memory chunks. It does not write a chunk corpus and does
not implement embeddings, vector or lexical indexes, retrieval, reranking,
generation, evaluation execution, an API, or persistence.

## Local loaders

`TextMarkdownLoader` accepts only `.md` and `.txt`. Files must exist, be regular
files, contain valid UTF-8, contain no NUL bytes, and contain non-empty text
after normalization.

`PyMuPDFLoader` accepts only `.pdf`. It hashes the original bytes and extracts
text page by page. Each non-empty page becomes a separate LangChain `Document`,
which keeps page citations possible during later retrieval. Password-protected,
corrupt, empty, and textless files fail with domain-specific errors.

The PDF adapter does not perform OCR. An image-only PDF therefore produces a
clear `EmptyInputError`; it is not reported as successfully parsed.

`FolderIngestionService` maps explicit extensions to injected loaders. Relative
paths are sorted case-insensitively with a deterministic tie-breaker before any
file is loaded. Unknown extensions fail by default. A caller may explicitly
select skip behavior and may inject a metadata provider for company and filing
attributes. All path inputs use `pathlib.Path`; no working-directory constants
or local absolute paths are stored in output metadata.

## Normalization

Normalization is deliberately conservative:

- CRLF and CR line endings become LF;
- non-breaking spaces become ordinary spaces;
- form-feed page breaks become line breaks;
- trailing spaces are removed;
- runs of excessive blank lines become one blank line;
- Markdown headings, indentation, pipe-delimited table rows, and internal
  spacing are not globally collapsed.

No standalone numbers, checkbox lines, or apparent page labels are deleted.
Those heuristics could remove legitimate financial content or provenance.

## Identifiers and metadata lineage

`document_id` is `doc_` plus the first 128 bits of a SHA-256 digest of the
original local file bytes. Identical bytes therefore receive the same stable ID
regardless of execution order. A changed file receives a changed ID.

`chunk_id` is `chunk_` plus the first 128 bits of a SHA-256 digest over a
canonical representation of the document ID, chunk index, page number, section
heading, and exact chunk text. It is deterministic for the same source and
chunking configuration while changing when content or lineage changes.

Every source `Document` validates these fields:

- `document_id`
- `source_file`
- `company`
- `filing_type`
- `filing_date`
- `page_number`
- `section_heading`

Every output chunk preserves those fields and adds:

- `chunk_id`
- `chunk_index`

`source_file` is a portable folder-relative display path, never an absolute
machine path. `page_number` is one-based for PDFs and `None` for ordinary text
or Markdown. `section_heading` is the nearest preceding ATX Markdown heading
when one is available; the pipeline does not invent headings for plain text.

## Chunking protocol

The defaults preserve the thesis experiment:

- `chunk_size=1500`
- `chunk_overlap=200`
- `min_chunk_chars=200`
- `keep_separator=True`
- separators, in order:
  `['\n# ', '\n## ', '\n### ', '\n\n', '\n', '. ', ' ', '']`

The configuration is a frozen Pydantic model and rejects an overlap greater
than or equal to the chunk size. Chunk indexes are sequential within each
document. Page documents are chunked independently, so no chunk crosses a PDF
page boundary and every PDF chunk retains an unambiguous page number.

The 200-character minimum is retained to avoid silently changing the thesis
parameter. If it removes every candidate chunk, Phase 1 raises `ChunkingError`
instead of silently returning an empty result.

## Differences from `research_legacy_v1`

The 15 thesis notebooks remain unchanged. Phase 1 migrates their useful
parameters and intent, but replaces notebook-only behavior:

- filename stems are replaced by content-derived document IDs;
- chunk IDs include content and lineage instead of only a filename and loop
  index;
- Pydantic schemas reject malformed or drifting metadata;
- global whitespace collapse is removed so Markdown/table-like structure is
  retained;
- PDF text is represented per page and page numbers survive chunking;
- section headings are derived and attached to chunks;
- folder order and supported extensions are explicit;
- loaders use typed domain errors instead of broad per-row exceptions;
- manifests, CSV/Parquet exports, ZIP creation, display cells, Kaggle branches,
  and hidden directory creation side effects are not part of the library.

The notebook used Docling to create Markdown and structured JSON. This Phase 1
scope instead uses the requested small local PyMuPDF text adapter. It does not
claim Docling-equivalent layout reconstruction, table recognition, or OCR.

## Known limitations

- Native PDF text extraction quality depends on the PDF's embedded text and
  reading order.
- Scanned/image-only pages require a future OCR adapter.
- Multi-column layouts, footnotes, headers, and ligatures may be ordered or
  encoded imperfectly by PyMuPDF.
- Tables in Markdown/text are preserved as text, but no semantic table model is
  built. PDF tables may lose row/column structure during extraction.
- Section metadata depends on ATX headings such as `# Heading`; plain PDF text
  usually has no reliable section label in this phase.
- Content-derived IDs detect byte changes, not semantic equivalence between two
  differently encoded files.
