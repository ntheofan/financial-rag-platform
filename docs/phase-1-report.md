# Phase 1 report — ingestion and chunking pipeline

Ημερομηνία: 2026-08-01

## Αποτέλεσμα

Η Φάση 1 ολοκληρώθηκε στο συμφωνημένο scope. Το repository περιέχει πλέον
offline, local pipeline από `.md`, `.txt` ή `.pdf` σε normalized LangChain
`Document` objects και έπειτα σε deterministic Markdown-aware chunks με πλήρες
metadata lineage.

Η υλοποίηση σταματά σε in-memory chunks. Δεν υλοποιήθηκαν embeddings, FAISS,
BM25, pgvector, reranking, OpenAI calls, FastAPI endpoints, database models,
Docker ή Streamlit. Δεν δημιουργήθηκε commit.

## Αρχεία που άλλαξαν

Υπάρχοντα αρχεία που ενημερώθηκαν:

- `README.md`
- `pyproject.toml`
- `src/financial_rag/core/__init__.py`
- `src/financial_rag/domain/__init__.py`
- `src/financial_rag/ingestion/__init__.py`
- `tests/test_package.py`

Νέα Phase 1 αρχεία:

- `src/financial_rag/core/errors.py`
- `src/financial_rag/domain/chunking.py`
- `src/financial_rag/domain/identifiers.py`
- `src/financial_rag/domain/metadata.py`
- `src/financial_rag/ingestion/base.py`
- `src/financial_rag/ingestion/loaders.py`
- `src/financial_rag/ingestion/normalization.py`
- `src/financial_rag/ingestion/service.py`
- `src/financial_rag/chunking/__init__.py`
- `src/financial_rag/chunking/sections.py`
- `src/financial_rag/chunking/service.py`
- `tests/unit/__init__.py`
- `tests/unit/chunking/__init__.py`
- `tests/unit/chunking/test_sections.py`
- `tests/unit/chunking/test_service.py`
- `tests/unit/domain/__init__.py`
- `tests/unit/domain/test_identifiers.py`
- `tests/unit/domain/test_metadata.py`
- `tests/unit/ingestion/__init__.py`
- `tests/unit/ingestion/test_loaders.py`
- `tests/unit/ingestion/test_normalization.py`
- `tests/unit/ingestion/test_service.py`
- `docs/data-pipeline.md`
- `docs/phase-1-report.md`

Δεν προστέθηκε κανένα PDF ή άλλο data fixture στο repository. Το synthetic PDF
του test δημιουργείται αποκλειστικά μέσα στο ignored pytest temporary directory
και διαγράφεται/αντικαθίσταται από το pytest lifecycle.

## Τεχνικές αποφάσεις

### Dependencies

Στα runtime dependencies προστέθηκαν μόνο όσα χρησιμοποιεί η Φάση 1:

- `langchain-core`
- `langchain-text-splitters`
- `PyMuPDF`

Το προηγούμενο μελλοντικό `rag` dependency group αφαιρέθηκε, επειδή δήλωνε
Docling, full LangChain, OpenAI, pandas, NumPy και sentence-transformers χωρίς να
χρησιμοποιούνται στο τρέχον scope. Τα Phase 0 future groups `api`, `storage`,
`evaluation` και `demo` παραμένουν declarations χωρίς implementation.

### Metadata contracts

Τα `SourceMetadata`, `DocumentMetadata` και `ChunkMetadata` είναι frozen Pydantic
v2 models με `extra="forbid"`. Τα output chunks έχουν ακριβώς:

`document_id`, `source_file`, `company`, `filing_type`, `filing_date`,
`page_number`, `section_heading`, `chunk_id`, `chunk_index`.

Το `source_file` πρέπει να είναι ασφαλές relative display path, ώστε να μη
διαρρέουν absolute local paths. Τα optional company/filing fields δεν
συμπληρώνονται με εικασίες.

### Deterministic identifiers

- `document_id`: SHA-256 των αρχικών file bytes, prefix `doc_`, 128-bit
  hexadecimal suffix.
- `chunk_id`: SHA-256 canonical payload με document ID, chunk index, page,
  section και ακριβές chunk text, prefix `chunk_`, 128-bit suffix.

Έτσι η ίδια είσοδος με την ίδια configuration παράγει τα ίδια IDs, ενώ αλλαγή
content ή lineage αλλάζει το σχετικό ID.

### Loading and PDF extraction

Ο text/Markdown loader απαιτεί local regular file, extension `.md` ή `.txt`,
strict UTF-8, μηδενικά NUL bytes και non-empty normalized content. Ο PDF adapter
χρησιμοποιεί PyMuPDF μόνο τοπικά, παράγει ένα LangChain `Document` ανά non-empty
page και διατηρεί one-based `page_number`.

Δεν γίνεται OCR. Corrupt, password-protected, empty και image-only/textless PDFs
αποτυγχάνουν με domain-specific errors.

### Normalization and chunking

Η normalization μετατρέπει line endings, NBSP και form feeds και περιορίζει τα
excess blank lines. Δεν κάνει global collapse στα spaces, δεν αφαιρεί standalone
page numbers και διατηρεί headings, indentation και pipe-delimited table-like
content.

Τα thesis parameters διατηρήθηκαν χωρίς σιωπηρή αλλαγή:

- `chunk_size=1500`
- `chunk_overlap=200`
- `min_chunk_chars=200`
- separators:
  `['\n# ', '\n## ', '\n### ', '\n\n', '\n', '. ', ' ', '']`
- `keep_separator=True`

Ο splitter καταγράφει start offsets, από τα οποία προκύπτει το nearest preceding
Markdown heading. Κάθε PDF page γίνεται chunk ανεξάρτητα, άρα κανένα chunk δεν
περνά page boundary. Αν το preserved 200-character minimum αφαιρέσει όλα τα
candidates, επιστρέφεται σαφές `ChunkingError` αντί για σιωπηρό empty result.

### Folder ingestion and logging

Το `FolderIngestionService` χρησιμοποιεί injected loader registry και optional
metadata provider. Τα paths ταξινομούνται deterministic με folder-relative,
case-insensitive key και tie-breaker. Τα supported extensions είναι ρητά
`.md`, `.pdf`, `.txt`. Unsupported files αποτυγχάνουν by default· skip γίνεται
μόνο με explicit opt-in.

Τα structured log events περιέχουν IDs, relative source names και counts, όχι
document content ή secrets.

## Verification commands και πραγματικά αποτελέσματα

### Requested Python install command

```powershell
py -3.12 -m pip install -e ".[dev]"
```

Πραγματικό αποτέλεσμα στο managed workspace: exit code `1` με
`No installed Python found!`. Ο Windows Python Launcher δεν έχει registered
Python installation, παρότι υπάρχει managed Python 3.12.13 runtime.

Η άμεση προσπάθεια μέσω του υπάρχοντος venv:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

απέτυχε επίσης με exit code `1`: `No module named pip`. Αυτό είναι ιδιότητα του
managed venv, όχι dependency-resolution failure του project.

Η εγκατάσταση ολοκληρώθηκε με το pip `--python` interface του managed Python
3.12 runtime:

```powershell
& '<managed Codex Python 3.12 executable>' -m pip `
  --python '.\.venv\Scripts\python.exe' install -e '.[dev]'
```

Το absolute managed runtime path έχει αντικατασταθεί σκόπιμα στο public report,
σύμφωνα με `docs/publication-policy.md`. Πραγματικό αποτέλεσμα: exit code `0`,
editable install `financial-rag-platform==0.1.0`. Εγκαταστάθηκαν μεταξύ άλλων
`langchain-core==1.5.3`, `langchain-text-splitters==1.1.2` και
`PyMuPDF==1.28.0`.

### Import smoke check

```powershell
.\.venv\Scripts\python.exe -c "import financial_rag; from financial_rag.chunking import MarkdownChunker; from financial_rag.ingestion import FolderIngestionService; print(financial_rag.__version__); print(FolderIngestionService().supported_extensions); print(MarkdownChunker().config.chunk_size)"
```

Πραγματικό αποτέλεσμα, exit code `0`:

```text
0.1.0
('.md', '.pdf', '.txt')
1500
```

Δεν έγινε network ή model call κατά το import.

### Ruff

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

Τελικά αποτελέσματα:

- lint: exit code `0`, `All checks passed!`
- format: exit code `0`, `42 files already formatted`

Στον πρώτο development pass το format check βρήκε τρία νέα Python files. Έγινε
μόνο mechanical `ruff format` σε αυτά και το τελικό check πέρασε.

### Mypy

```powershell
.\.venv\Scripts\mypy.exe src tests
```

Τελικό αποτέλεσμα: exit code `0`,
`Success: no issues found in 32 source files`.

Ο πρώτος pass εντόπισε duplicate test module names και missing typings στο
third-party PyMuPDF surface. Προστέθηκαν test package boundaries και
περιορισμένα `no-untyped-call` ignores αποκλειστικά στα δύο PyMuPDF constructor
calls. Όλος ο δικός μας κώδικας παραμένει strict typed.

### Pytest and coverage

```powershell
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Τελικό αποτέλεσμα: exit code `0`, `42 passed in 1.34s`, συνολική line/branch
coverage αναφορά `92%` (`313` statements, `16` missed, `74` branches). Αυτό είναι
coverage της μικρής Phase 1 library και δεν αποτελεί production-readiness claim.

Στον πρώτο pass, το default Windows pytest temp root δεν ήταν writable στο
managed sandbox και ένα normalization assertion αποκάλυψε ότι διατηρούνταν δύο
blank lines. Το pytest `--basetemp` μεταφέρθηκε στο ήδη ignored
`.cache/pytest-tmp`, και η normalization ευθυγραμμίστηκε με το notebook rule
`3+ newlines -> 2`. Το τελικό exact command παραπάνω περνά χωρίς environment
override.

### Git and publication boundary

```powershell
git status --short --ignored
```

Πραγματικό αποτέλεσμα: exit code `0`. Τα Phase 0 και Phase 1 public candidate
files εμφανίζονται ως `??`, ενώ `.cache`, `.coverage`, tool caches, `.venv`,
egg-info, πραγματικά data artifacts, PDFs, processed chunks/embeddings/results,
τα 15 notebooks και notebook figures εμφανίζονται ως `!!` ignored.

Υπάρχει σημαντική απόκλιση από το αναμενόμενο baseline: το τρέχον Git repository
αναφέρει `No commits yet on master`. Επομένως δεν υπάρχει διαθέσιμο baseline
commit και το Git δεν μπορεί να ξεχωρίσει Phase 0 από Phase 1 μέσω diff. Δεν έγινε
`git add`, commit, branch, move ή delete στη Φάση 1.

Το επιπλέον command:

```powershell
git ls-files --others --exclude-standard
```

επιβεβαίωσε ότι τα non-ignored candidates περιορίζονται σε source code, tests,
documentation/configuration, τα τρία `data/**/.gitkeep` και τα Phase 0 README/
license files. Δεν εμφανίστηκε `.env`, PDF, parsed/cleaned text, chunk corpus,
embedding, index, context, database ή FinanceBench artifact.

### Notebook integrity

```powershell
Get-ChildItem notebooks -Filter *.ipynb |
  Sort-Object Name |
  Get-FileHash -Algorithm SHA256
```

Τα τελικά hashes συγκρίθηκαν με τα 15 baseline hashes του audit:
`notebooks=15`, `unchanged=15`, `changed=0`.

## Τι διατηρήθηκε αμετάβλητο

- Και τα 15 thesis notebooks παραμένουν byte-for-byte αμετάβλητα και ignored.
- Κανένα υπάρχον data file δεν μετακινήθηκε, διαγράφηκε ή αντιγράφηκε.
- Δεν εκτελέστηκε notebook και δεν δημιουργήθηκε parsed text ή persistent chunk
  output.
- Το `research_legacy_v1` παραμένει historical artifact με τα υπάρχοντα caveats.
- Δεν προστέθηκαν secrets, `.env`, πραγματικά PDFs ή FinanceBench rows.
- Τα packages `retrieval`, `generation`, `evaluation`, `api` και `storage`
  παραμένουν χωρίς Phase 1 business implementation.
- Δεν έγιναν live OpenAI, model download κατά tests, database ή network calls.

## Scope της Φάσης 2 — retrieval

Η Φάση 2 δεν έχει ξεκινήσει. Με νέα έγκριση θα πρέπει να καλύψει ξεχωριστά:

- embedding provider interface και local BAAI/bge-m3 adapter,
- production vector-storage boundary για PostgreSQL/pgvector,
- dense retrieval με σαφή cosine/IP semantics,
- BM25 lexical retrieval και deterministic Reciprocal Rank Fusion,
- `dense`, `hybrid`, `hybrid_reranked` modes με κοινό result schema,
- BAAI/bge-reranker-v2-m3 adapter και διορθωμένο candidate pool,
- versioned `platform_v1` configuration δίπλα στο immutable
  `research_legacy_v1`,
- deterministic ranking/tie-breaking tests χωρίς model downloads ή external
  calls στα automated tests.

Η Φάση 1 σταματά εδώ και αναμένει review/έγκριση.
