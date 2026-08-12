# Phase 2 report — retrieval layer

Ημερομηνία: 2026-08-01

## Αποτέλεσμα

Η Φάση 2 ολοκληρώθηκε στο συμφωνημένο scope. Το `platform_v1` παρέχει πλέον
modular, offline-testable retrieval layer για:

- V1: dense retrieval,
- V2: dense + BM25 + weighted Reciprocal Rank Fusion,
- V3: hybrid candidate union + cross-encoder reranking.

Η υλοποίηση σταματά στο ranked `RetrievalResult`. Δεν δημιουργεί generation
context, απάντηση ή evaluation metric. Δεν εκτελέστηκε πραγματικό FinanceBench
indexing, BGE-M3 inference ή benchmark run και δεν γίνεται claim ότι
αναπαράγονται τα historical thesis metrics του `research_legacy_v1`.

Δεν υλοποιήθηκαν PostgreSQL/pgvector, FastAPI, OpenAI, generation, evaluation,
Docker ή Streamlit. Δεν έγινε Git commit ή push.

## Αρχεία που άλλαξαν

Υπάρχοντα αρχεία που ενημερώθηκαν:

- `.gitignore`
- `README.md`
- `pyproject.toml`
- `configs/README.md`
- `scripts/README.md`
- `src/financial_rag/core/__init__.py`
- `src/financial_rag/core/errors.py`
- `src/financial_rag/domain/__init__.py`
- `src/financial_rag/retrieval/__init__.py`

Νέα configuration/domain/retrieval αρχεία:

- `configs/retrieval/platform_v1.json`
- `src/financial_rag/domain/fingerprints.py`
- `src/financial_rag/domain/retrieval.py`
- `src/financial_rag/retrieval/artifacts.py`
- `src/financial_rag/retrieval/bm25.py`
- `src/financial_rag/retrieval/corpus.py`
- `src/financial_rag/retrieval/dense.py`
- `src/financial_rag/retrieval/embeddings.py`
- `src/financial_rag/retrieval/fusion.py`
- `src/financial_rag/retrieval/hits.py`
- `src/financial_rag/retrieval/manifests.py`
- `src/financial_rag/retrieval/protocols.py`
- `src/financial_rag/retrieval/query_expansion.py`
- `src/financial_rag/retrieval/rerankers.py`
- `src/financial_rag/retrieval/service.py`
- `src/financial_rag/retrieval/vectors.py`

Νέα ή ενημερωμένα test αρχεία:

- `tests/__init__.py`
- `tests/unit/retrieval/__init__.py`
- `tests/unit/retrieval/helpers.py`
- `tests/unit/retrieval/test_artifacts.py`
- `tests/unit/retrieval/test_config_and_manifests.py`
- `tests/unit/retrieval/test_embeddings.py`
- `tests/unit/retrieval/test_fusion.py`
- `tests/unit/retrieval/test_indexes.py`
- `tests/unit/retrieval/test_query_expansion.py`
- `tests/unit/retrieval/test_service.py`

Νέα documentation:

- `docs/retrieval-design.md`
- `docs/cloud-indexing.md`
- `docs/phase-2-report.md`

## Τεχνικές αποφάσεις

### Dependencies και model boundary

Στο runtime προστέθηκαν μόνο `numpy` και `faiss-cpu`. Δεν προστέθηκε
`rank-bm25`, επειδή η μικρή custom BM25 υλοποίηση διατηρεί ακριβώς τον positive
IDF τύπο του notebook και παραμένει πλήρως ορατή/testable.

Το `FlagEmbedding>=1.4,<2` είναι μόνο optional `[models]` extra. Δεν
εγκαθίσταται από `.[dev]` και δεν απαιτείται από tests/CI. Τα
`BgeM3EmbeddingProvider` και `BgeM3Reranker` είναι lazy: import, constructor και
package smoke tests δεν φορτώνουν FlagEmbedding, weights, network ή GPU.

Το πραγματικό model load γίνεται μόνο στην πρώτη explicit encode/score κλήση.
Οι adapters δέχονται `cpu`, `cuda` ή `auto`, explicit batch size και `use_fp16`.
Τα tests ελέγχουν την adapter API με injected synthetic FlagEmbedding surface,
όχι με πραγματικά weights.

### Versioned `platform_v1` protocol

Το `configs/retrieval/platform_v1.json` κρατά:

- `BAAI/bge-m3`, dimension `1024`, L2 normalization,
- FAISS `IndexFlatIP`,
- BM25 `k1=1.5`, `b=0.75`,
- dense/BM25 candidates `20/10`,
- weighted RRF `k=30`, weights `1.0/0.2`,
- final top-k `10`,
- `BAAI/bge-reranker-v2-m3`,
- versioned `finance_aliases_v1` rules.

Το πλήρες validated config έχει canonical SHA-256 fingerprint. Τα contracts
είναι frozen Pydantic v2 models με `extra="forbid"`.

### Dense retrieval

Ο FAISS adapter απαιτεί inner-product metric, σωστή dimension, finite/non-zero
vectors και ακριβή row-count alignment. Corpus και query vectors
L2-normalize-άρονται στο index boundary. Σε unit vectors το inner product δίνει
το ίδιο ranking με cosine similarity. Τα equal scores ταξινομούνται σταθερά με
`chunk_id`.

### BM25 και RRF

Το BM25 χρησιμοποιεί το notebook token pattern `[a-zA-Z0-9&\.]+`, τον ίδιο
positive IDF τύπο και deterministic score/`chunk_id` ordering.

Το weighted RRF συγχωνεύει dense/BM25 duplicates, εμποδίζει conflicting row
mappings και αγνοεί δεύτερη εμφάνιση του ίδιου chunk μέσα σε έναν retriever.
Ties λύνονται με best component rank και μετά `chunk_id`.

### V1/V2/V3 service

Μία `RetrievalService` συνθέτει και τις τρεις routes χωρίς duplicate business
logic. Η αναζήτηση είναι document-unknown πάνω σε ολόκληρο το indexed corpus.

- V1 κρατά dense top-10.
- V2 κάνει fusion του dense-20 και BM25-10 pool και κρατά top-10.
- V3 rerank-άρει ολόκληρο το unique hybrid union και μόνο μετά κρατά top-10.

Ο reranker identifier πρέπει να συμφωνεί με το versioned config. Χωρίς explicit
reranker, το V3 αποτυγχάνει με `RerankerRequiredError` αντί να υποβαθμίζεται
σιωπηρά σε V2.

### Metadata lineage και query expansion

Κάθε `RetrievedChunk` διατηρεί όλα τα Phase 1 fields:

`document_id`, `source_file`, `company`, `filing_type`, `filing_date`,
`page_number`, `section_heading`, `chunk_id`, `chunk_index`.

Προσθέτει exact content, final rank και transparent dense/BM25/RRF/reranker
scores. Η alias expansion είναι deterministic, longest-alias-first,
de-duplicated και μέρος του retrieval config fingerprint.

### Local artifacts και compatibility

Το artifact adapter γράφει μόνο σε explicit `pathlib.Path`:

- `index.faiss`,
- `chunks.retrieval.json`,
- `manifest.retrieval.json`.

Τα patterns και τα temporary variants είναι ignored. Το manifest περιέχει model,
dimension, normalization, chunking fingerprint, ordered full chunk-mapping
fingerprint, FAISS vector fingerprint, corpus count, retrieval config
fingerprint, timezone-aware timestamp και artifact version.

Load απορρίπτει incompatible model/dimension/normalization/chunking, mapping
tampering/reordering, mixed FAISS file, count/dimension mismatch και non-IP
index. Το multi-file save δεν παρουσιάζεται ως database transaction· τα
fingerprints και το manifest-last write κάνουν interrupted/mixed sets detectable.

## Tests

Προστέθηκαν αποκλειστικά synthetic/offline tests για:

- deterministic fake embeddings και L2 normalization,
- shape/dimension/non-finite/zero-vector validation,
- FAISS dense ranking και rejection non-IP index,
- BM25 ranking και stable ties,
- weighted RRF formula, tie-breaking και duplicates,
- V1/V2/V3 routing και score transparency,
- fake reranking που αλλάζει σκόπιμα το full-pool ranking,
- deterministic finance query expansion,
- config/mapping/vector fingerprints και manifest compatibility,
- artifact round-trip, incomplete/mixed/tampered artifact rejection,
- Phase 1 metadata preservation μέχρι `RetrievedChunk`,
- lazy model adapters χωρίς πραγματικό import/download/weights/GPU,
- empty corpus/query και provider/reranker configuration failures.

Δεν δημιουργήθηκε ή αποθηκεύτηκε πραγματικό corpus artifact. Τα synthetic
artifact round-trips εκτελούνται μόνο κάτω από το ignored pytest temp root.

## Verification commands και πραγματικά αποτελέσματα

### Install

```powershell
py -3.12 -m pip install -e ".[dev]"
```

Πραγματικό αποτέλεσμα στο managed workspace: exit code `1`,
`No installed Python found!`. Ο Windows Python Launcher δεν έχει registered
Python, όπως και στη Φάση 1.

Η εγκατάσταση έγινε επιτυχώς μέσω του pip `--python` interface του managed
Python 3.12 runtime:

```powershell
& '<managed Codex Python 3.12 executable>' -m pip `
  --python '.\.venv\Scripts\python.exe' install -e '.[dev]'
```

Το absolute runtime path έχει sanitized σύμφωνα με την publication policy.
Πραγματικό αποτέλεσμα: exit code `0`, editable install
`financial-rag-platform==0.1.0`, `faiss-cpu==1.14.3`, `numpy==2.5.1`.
Το optional `[models]` extra και FlagEmbedding δεν εγκαταστάθηκαν.

### Import smoke check

```powershell
.\.venv\Scripts\python.exe -c "import financial_rag; from financial_rag.domain import RetrievalConfig; from financial_rag.retrieval import BgeM3EmbeddingProvider, BgeM3Reranker, FakeEmbeddingProvider, RetrievalService; from pathlib import Path; config = RetrievalConfig.from_json_file(Path('configs/retrieval/platform_v1.json')); print(financial_rag.__version__); print(config.platform_version, config.embedding_dimension, config.fingerprint.value[:12]); print(BgeM3EmbeddingProvider().is_loaded, BgeM3Reranker().is_loaded); print(FakeEmbeddingProvider().normalization_method)"
```

Πραγματικό αποτέλεσμα: exit code `0`:

```text
0.1.0
platform_v1 1024 de446ef9af6b
False False
l2
```

Τα δύο real-model adapters παρέμειναν unloaded.

### Ruff, Mypy και Pytest

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing -q
```

Τελικά αποτελέσματα:

- Ruff lint: exit code `0`, `All checks passed!`
- Ruff format: exit code `0`, `70 files already formatted`
- Mypy strict: exit code `0`, `Success: no issues found in 57 source files`
- Pytest: exit code `0`, `81 passed`
- συνολική coverage: `90%`

Η coverage είναι test evidence για το τρέχον μικρό library scope, όχι
production-readiness ή benchmark claim.

### Git/publication boundary

```powershell
git status --short --ignored
git check-ignore -v `
  data\processed\retrieval_index\platform_v1\index.faiss `
  data\processed\retrieval_index\platform_v1\chunks.retrieval.json `
  data\processed\retrieval_index\platform_v1\manifest.retrieval.json `
  .env
```

Το status επέστρεψε exit code `0`. Τα source/docs/config/tests εμφανίζονται ως
untracked public candidates. `.env`, `.cache`, `.venv`, data, PDFs, historical
chunks/embeddings/results, notebooks, notebook figures, generated retrieval
artifacts και model/tool caches εμφανίζονται ignored.

Το `git check-ignore` επιβεβαίωσε ότι και τα τρία representative retrieval
artifacts καλύπτονται από `/data/processed/*`, ενώ `.env` καλύπτεται από τη
dedicated secret rule.

Παραμένει η Git απόκλιση των προηγούμενων phases: το repository αναφέρει
`No commits yet on master`, επομένως δεν υπάρχει ορατό Phase 1 baseline commit
για diff. Δεν έγινε `git add`, commit, branch, push, move ή delete.

### Notebook integrity και secret/path scan

```powershell
Get-ChildItem notebooks -Filter *.ipynb |
  Sort-Object Name |
  Get-FileHash -Algorithm SHA256
```

Σύγκριση με το audit baseline: `notebooks=15`, `unchanged=15`, `changed=0`.

Το public-candidate scan για `C:\Users\` και literal secret pattern
`sk-[A-Za-z0-9_-]{16,}` δεν επέστρεψε match.

## Τι παρέμεινε αμετάβλητο

- Τα 15 thesis notebooks παρέμειναν byte-for-byte αμετάβλητα και δεν
  εκτελέστηκαν/μορφοποιήθηκαν.
- Κανένα historical result ή υπάρχον data artifact δεν άλλαξε, μετακινήθηκε ή
  διαγράφηκε.
- Δεν προστέθηκε πραγματικό PDF, chunk corpus, embedding matrix, FAISS index,
  model cache, context, `.env` ή secret.
- Το `research_legacy_v1` και τα historical metrics παρέμειναν μόνο historical
  thesis artifacts.
- Τα Phase 1 ingestion/chunking defaults και contracts δεν άλλαξαν.
- Δεν έγινε OpenAI, external service, database, GPU ή actual model call.

## Γνωστοί περιορισμοί

- Το real BGE-M3 και reranker execution δεν δοκιμάστηκε με weights στη Φάση 2.
- Το `IndexFlatIP` είναι exact/in-memory και δεν αποτελεί scaling solution.
- Το BM25 index είναι in-memory και ο thesis-compatible ASCII tokenizer δεν
  καλύπτει πλήρως multilingual text.
- Η alias matching είναι deterministic substring matching, όχι linguistic
  entity recognition.
- Τα local artifact files δεν είναι transactional database records, παρότι
  fingerprints ανιχνεύουν incomplete, tampered και mixed sets.
- Δεν υπάρχει corpus revision store, pgvector persistence, API lifecycle,
  authentication, multi-user isolation ή benchmark runner.

## Scope της Φάσης 3

Η Φάση 3 δεν ξεκίνησε. Με νέα έγκριση μπορεί να είναι persistence/
pgvector-oriented storage ή API design και να καλύψει ενδεικτικά:

- PostgreSQL/pgvector document, chunk και embedding persistence,
- SQLAlchemy 2.0 repositories και Alembic migrations,
- corpus/index revision lifecycle και durable compatibility metadata,
- ή typed FastAPI design πάνω από τα υπάρχοντα Phase 1/2 services.

Δεν ανήκουν στη Φάση 2 generation, OpenAI calls, evaluation execution,
Streamlit, Docker deployment ή public scaling claims.

Η Φάση 2 σταματά εδώ και αναμένει review/έγκριση.
