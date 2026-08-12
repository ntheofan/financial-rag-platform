# Notebook Migration Audit — `financial-rag-platform`

Ημερομηνία audit: 2026-08-01

## 1. Απόφαση του audit

Το repository περιέχει μια ουσιαστική και ολοκληρωμένη ερευνητική ροή RAG, αλλά όχι ακόμη ένα αναπαραγώγιμο application repository. Υπάρχουν χρήσιμοι αλγόριθμοι και πραγματικά experimental artifacts για ingestion, retrieval, reranking, generation και evaluation. Δεν υπάρχουν όμως package, API, database schema, tests, dependency/configuration management, containers, CI ή public-repository hygiene.

Η σωστή στρατηγική δεν είναι να μεταφερθούν αυτούσια notebook cells σε endpoints. Πρέπει να εξαχθούν οι καθαρές συναρτήσεις και οι πειραματικές παράμετροι σε domain services με ρητά interfaces, typed schemas και versioned run configuration. Τα notebooks παραμένουν αμετάβλητα ως research artifacts και δεν αποτελούν runtime dependency της πλατφόρμας.

Μέχρι να ολοκληρωθούν τα provenance και data-publication gates που περιγράφονται παρακάτω, τα υπάρχοντα metrics πρέπει να παρουσιάζονται μόνο ως **research artifacts**, όχι ως αναπαραγώγιμα production benchmarks.

## 2. Scope και μέθοδος

Διαβάστηκαν:

- και τα 15 notebooks, μαζί με cell types, source, metadata και αποθηκευμένα outputs,
- όλο το ορατό repository inventory,
- όλα τα CSV/JSON/JSONL schemas και manifests εκτός από την πλήρη επανάληψη του κειμένου των 84 filings,
- αντιπροσωπευτικά Docling JSON και Markdown artifacts,
- τα stored retrieval, QA, RAGAS, RAGChecker και error-analysis results,
- η κατάσταση Git και η παρουσία README/configuration/tooling files,
- οι public πληροφορίες προέλευσης και άδειας του FinanceBench.

Δεν τροποποιήθηκε κανένα notebook και δεν γράφτηκε production code. Το μόνο νέο αρχείο αυτής της φάσης είναι το παρόν audit.

## 3. Τι υπάρχει σήμερα

### 3.1 Repository και Git

- Το repository έχει `.git`, αλλά δεν έχει κανένα commit (`No commits yet on master`).
- Όλα τα υπάρχοντα αρχεία είναι untracked.
- Στο root υπάρχουν μόνο `data/` και `notebooks/` πριν από τη δημιουργία του παρόντος `docs/`.
- Δεν υπάρχουν `README`, `LICENSE`, `.gitignore`, `.gitattributes`, `.env.example`, `pyproject.toml`, requirements/lock file, Docker files, CI workflows ή pre-commit configuration.
- Δεν υπάρχει `src/`, `tests/`, FastAPI app, Streamlit app, database model ή Alembic migration.
- Δεν βρέθηκε hardcoded OpenAI key. Τα notebooks αναφέρονται μόνο στο `OPENAI_API_KEY` μέσω environment variable. Επειδή δεν υπάρχει `.gitignore`, ένα μελλοντικό `.env` θα ήταν άμεσα εκτεθειμένο σε accidental commit.

### 3.2 Μέγεθος και περιεχόμενο

| Περιοχή | Περιεχόμενο | Παρατήρηση |
|---|---|---|
| `notebooks/` | 15 notebooks, 14 generated PNG figures | ~4,35 MB συνολικά· ορισμένα notebooks κρατούν outputs, άλλα είναι stripped |
| `data/raw/` | 2 FinanceBench JSONL και 88 PDFs | ~161,31 MB |
| `data/interim/` | 84 Docling JSON, 84 Markdown, 84 cleaned Markdown, manifests | ~755,62 MB |
| `data/processed/` | chunks, embeddings, FAISS, retrieval/QA/evaluation results | ~388,03 MB |
| συνολικό `data/` | 424 files | ~1,305 GB |

Δύο αρχεία embeddings είναι περίπου 144,68 MB το καθένα και υπερβαίνουν το κανονικό GitHub file limit. Το repository δεν πρέπει να χρησιμοποιήσει Git LFS ως υποκατάστατο σωστής data policy: raw PDFs, parsed documents, embeddings, vector indexes, generated contexts και local run outputs πρέπει να παραμείνουν local/ignored artifacts.

### 3.3 Dataset snapshot

- `financebench_open_source.jsonl`: 150 μοναδικές ερωτήσεις, 32 εταιρείες, 84 έγγραφα.
- Οι τρεις κατηγορίες ερωτήσεων είναι ισομερώς κατανεμημένες: 50 `domain-relevant`, 50 `metrics-generated`, 50 `novel-generated`.
- `financebench_document_information.jsonl`: 361 rows, 360 unique document names και 40 εταιρείες. Περιέχει δηλαδή ευρύτερο document catalog από τα 84 documents του open-source question subset.
- Τα 88 local PDFs καλύπτουν και τα 84 referenced documents. Τέσσερα PDFs δεν χρησιμοποιούνται από τις 150 ερωτήσεις:
  - `AMCOR_2022_8K_2022-07-01.pdf`
  - `JOHNSON_JOHNSON_2023_8K_dated-2023-08-23.pdf`
  - `JPMORGAN_2022Q3_10Q.pdf`
  - `ULTABEAUTY_2023Q1_EARNINGS.pdf`
- Το document information έχει duplicate `FOOTLOCKER_2023_annualreport` με διαφορετικό `doc_period` (2022 και 2023), άρα χρειάζεται explicit validation/deduplication policy.
- Και τα 84 parse, cleaning και chunking manifest rows έχουν `success` status.

Το Hugging Face dataset card δηλώνει άδεια [CC BY-NC 4.0](https://huggingface.co/datasets/PatronusAI/financebench). Το [official FinanceBench repository](https://github.com/patronus-ai/financebench) περιγράφει το open-source sample των 150 ερωτήσεων, τα evidence fields και τα source PDFs και ζητά citation του paper. Αυτό δεν αποτελεί αυτόματη επιβεβαίωση ότι κάθε εταιρικό PDF ή κάθε derived full-text artifact μπορεί να αναδημοσιευθεί χωρίς περιορισμό. Η ασφαλής προεπιλογή για το public portfolio είναι:

1. να μη γίνουν commit τα PDFs ή τα derived full-text/embedding artifacts,
2. να παρέχεται downloader/importer που δείχνει στην επίσημη πηγή,
3. να υπάρχει `DATA_LICENSE.md` με attribution και non-commercial restriction του benchmark,
4. να περιλαμβάνεται μόνο μικρό synthetic fixture για tests/demo,
5. να προηγηθεί manual publication review για τα saved notebook outputs, επειδή περιέχουν αποσπάσματα, answers και προσωπικά absolute paths.

### 3.4 Υπάρχουσα ερευνητική pipeline

Η πραγματική ροή που προκύπτει από τα notebooks είναι:

1. bootstrap/download του FinanceBench sample και αντιστοίχιση document names με PDFs,
2. PDF parsing με Docling σε Markdown και structured JSON,
3. heuristic Markdown cleaning,
4. recursive Markdown-aware chunking,
5. normalized `BAAI/bge-m3` embeddings και FAISS `IndexFlatIP`,
6. global, document-unknown dense retrieval με finance-aware query expansion,
7. hybrid retrieval με custom BM25 και weighted Reciprocal Rank Fusion,
8. cross-encoder reranking με `BAAI/bge-reranker-v2-m3`,
9. answer generation με explicit prompt και OpenAI SDK,
10. deterministic retrieval/answer evaluation, RAGAS, RAGChecker, error analysis και thesis figures.

Stored artifacts δείχνουν:

- 84 documents,
- 37.037 chunks,
- 1.024-dimensional embeddings,
- 150 queries και 1.500 result rows ανά retrieval mode,
- επιτυχές manifest status για 150/150 queries σε dense, hybrid και reranked runs.

Οι stored research retrieval metrics είναι:

| Mode | Evidence Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---:|---:|---:|---:|
| Dense | 0,1667 | 0,3200 | 0,3800 | 0,2575 |
| Hybrid | 0,1867 | 0,3000 | 0,3867 | 0,2671 |
| Hybrid + reranker | 0,2600 | 0,3733 | 0,4467 | 0,3280 |

Αυτά είναι χρήσιμα ως historical baseline, αλλά δεν είναι ακόμη αποδεκτό reproducibility claim λόγω των αποκλίσεων source/artifact της ενότητας 6.

## 4. Audit ανά notebook

| Notebook | Τι κάνει | Χρήσιμο για migration | Notebook-only / πρόβλημα |
|---|---|---|---|
| `01_setup_and_config` | paths, directory bootstrap, seed, `.env` load | naming και αρχική λίστα settings | αναφέρεται σε ανύπαρκτα JSON configs, δημιουργεί dirs ως side effect, suppresses warnings, Python 3.11 metadata |
| `02_prepare_financebench_dataset` | HF bootstrap, PDF download, merge/matching, working dataset | downloader, URL resolver, filename normalization, manifest idea | duplicated `normalize_text`, no checksum/content validation, synchronous network I/O, no license gate, broad catalog vs sample ambiguity |
| `03_parse_pdfs_with_docling` | PDF → Markdown + Docling JSON | `parse_pdf_with_docling`, per-document status manifest | local/Kaggle path branching, sequential long job, broad exceptions, ZIP side effects, no durable job model |
| `04_clean_and_inspect_documents` | heuristic cleanup και inspection | `clean_markdown` ως αρχικό pure transform | αφαιρεί standalone page numbers και χάνει provenance, heuristics μη versioned, global whitespace normalization, inspection/display/ZIP code |
| `05_create_chunks` | recursive heading-aware chunking | separators, base parameters 1500/200, chunk ID concept | το source δηλώνει `table_aware` χωρίς να υλοποιεί table-aware splitter, δεν κρατά page/section offsets, drops chunks κάτω από 200 chars, token count είναι `len/4` |
| `06_create_embeddings_and_vectorstore` | BGE-M3 embeddings, normalization, FAISS | batching/normalization και metadata alignment checks | research-only FAISS/NPY/Pickle, eager model load, no provider interface, no persistence transaction/version/hash |
| `07_dense_retrieval` | global dense baseline και query expansion | finance alias map, explicit FAISS cosine logic | ξαναχτίζει index αντί να φορτώνει το saved index, configs μέσα στο cell, conclusion λέει λανθασμένα document-known, expected document fields συνυπάρχουν στα outputs |
| `08_hybrid_retrieval` | custom BM25 + weighted RRF | tokenization, BM25 formula, transparent component scores, RRF | BM25 κάνει full Python scan/count ανά token και query, hardcoded weights, ~3:34 για 150 queries στο saved output, inconsistent docstrings |
| `09_reranking` | BGE cross-encoder πάνω σε hybrid results | μικρή καθαρή `rerank_candidates` | `RERANK_TOP_N=20`, αλλά το input έχει μόνο top-10· no batching/device abstraction/latency metadata |
| `10_answer_generation` | context assembly, prompt, OpenAI generation | explicit prompt, context labels, abstention text, SDK boundary | δεν επιστρέφει structured citations, no page/section, duplicated multi-run logic βρίσκεται σε **markdown cell και δεν εκτελείται**, dry-run output μπορεί να μετρηθεί ως success |
| `11_evaluate_retrieval_and_qa` | Hit@K, MRR, lexical F1, substring, context support | pure deterministic metric seeds και comparison table | evidence match είναι unvalidated token-set F1 threshold 0,3, missing queries μπορούν να χαθούν, component scores δεν είναι συγκρίσιμα, reranked “best score” διαβάζει RRF αντί rerank score |
| `12_error_analysis` | rule-based failure taxonomy και cross-run analysis | χρήσιμη ταξινομία και qualitative workflow | duplicate metric logic, threshold drift, document-level retrieval success δεν ισοδυναμεί με evidence success, saved outputs δεν συμφωνούν με το current threshold |
| `13_ragas_evaluation` | optional RAGAS evaluation | dataset adapter και explicit metric selection | live LLM evaluator, version-sensitive API, zero-valued placeholders για skipped runs, notebook event-loop patches, ZIP side effect |
| `14_ragchecker_evaluation` | RAGChecker schema conversion/evaluation | schema adapter και status/error capture | ολόκληρο `context_text` μετατρέπεται σε ένα context chunk, skipped/failed runs γράφουν μηδενικά metrics, consolidated cell είναι πολύ μεγάλο |
| `15_thesis_figures_and_tables` | 14 figures/tables | research presentation layer και historical charts | hardcoded axes/scales, δεν ελέγχει metric status/provenance, assumes percentage units, duplicated lexical metric, label typo `??Figure 2` |

## 5. Κώδικας που αξίζει να μεταφερθεί

Δεν πρέπει να αντιγραφούν ολόκληρα cells. Αξίζει να μεταφερθεί και να καλυφθεί με tests η λογική των παρακάτω περιοχών:

- dataset normalization, document matching και safe filename generation,
- Docling conversion και η ιδέα των per-document manifests,
- deterministic Markdown cleanup ως versioned transform,
- Markdown-aware separator strategy και stable chunk IDs,
- BGE embedding normalization και explicit inner-product/cosine semantics,
- finance alias/query-expansion map ως **προαιρετικό, versioned preprocessing step**,
- custom BM25 formula και weighted RRF με πλήρη component-score trace,
- cross-encoder reranker,
- explicit system/user prompt και abstention policy,
- Hit@K, MRR, lexical metrics και failure taxonomy, αφού διορθωθούν και οριστούν συμβόλαια,
- RAGAS/RAGChecker adapters ως optional, non-CI evaluators και όχι ως core runtime.

Η Docling structured JSON έχει ήδη `prov.page_no`, bounding boxes και table objects. Το σημερινό Markdown pipeline τα πετάει. Η production migration πρέπει να χτίσει chunks από structured document elements ή από page-tagged intermediate records, ώστε κάθε chunk να κρατά `page_start`, `page_end`, `section_path` και προαιρετικά bounding-box provenance.

Προτεινόμενη αντιστοίχιση σε package modules:

```text
src/financial_rag/
  api/                 FastAPI routes, request/response schemas, dependencies
  core/                settings, logging, errors, IDs, hashing
  domain/              document/chunk/query/evaluation entities and protocols
  db/                  SQLAlchemy models, repositories, pgvector integration
  ingestion/           import, validation, Docling parse, cleaning, chunking
  retrieval/           dense, BM25, RRF, reranker, query preprocessing
  generation/          prompt, context budget, OpenAI adapter, citations
  evaluation/          benchmark loaders, metrics, run manifests, reports
  worker/              durable PostgreSQL-backed ingestion/evaluation jobs
apps/
  streamlit_app.py
alembic/
tests/
  unit/
  integration/
  api/
  fixtures/
```

Η business logic θα εξαρτάται από μικρά protocols (`EmbeddingProvider`, `VectorRepository`, `Reranker`, `AnswerGenerator`) και όχι από LangChain chains. LangChain/OpenAI/Docling/SQLAlchemy θα είναι adapters στα άκρα.

## 6. Κρίσιμες αποκλίσεις και reproducibility risks

### 6.1 Source code και artifacts δεν αντιστοιχούν

Υπάρχουν πολλαπλές ενδείξεις ότι τα stored artifacts παράχθηκαν από διαφορετικές εκδόσεις κώδικα ή διαφορετικά working directories:

- Το current chunking source δεν υλοποιεί table-aware logic, αλλά το CSV έχει `is_table_chunk`/`has_table_header` και το stats JSON αναφέρει 7.202 table chunks.
- Το current embedding notebook έχει batch size 8, ενώ το stored manifest/stats αναφέρει 64.
- Το current generation notebook έχει `gpt-4o-mini`, ενώ τα QA stats αναφέρουν `gpt-5.4-mini`.
- Dense, reranked και hybrid stats/manifests περιέχουν absolute paths από διαφορετικά directories (`financial-rag-final`, `Financial-RAG/thesis-rag`, Kaggle).
- Τα stored error stats για hybrid/reranked χρησιμοποιούν threshold 0,5, ενώ το current notebook ορίζει 0,3 και τα saved outputs του ανοιχτού notebook δείχνουν διαφορετικά cross-run percentages από ορισμένα JSON files.
- Τα notebooks έχουν ασυνεπή kernel/language metadata (3.11, 3.12, 3.13 και μη αξιόπιστες `2.7.6` τιμές σε ορισμένα metadata fields).

Απαιτείται `RunManifest` με code revision, config hash, corpus snapshot hash, model IDs/revisions, package versions, timestamp, seed, mode και metric status. Τα historical outputs δεν πρέπει να overwrite-άρονται.

### 6.2 Η σημερινή σύγκριση δεν είναι πλήρως ελεγχόμενη

- Dense και hybrid χρησιμοποιούν query expansion, αλλά αυτό είναι baked μέσα στα modes και όχι ανεξάρτητος ablation factor.
- Hybrid παράγει μόνο top-10, άρα το reranker που ζητά 20 candidates βλέπει τελικά μόνο 10. Το stored `previous_rank` επιβεβαιώνει range 1–10.
- RRF χρησιμοποιεί dense weight 1,0 και BM25 weight 0,2 χωρίς versioned tuning record.
- Τα raw dense, BM25, RRF και reranker scores βρίσκονται σε διαφορετικές κλίμακες· το UI πρέπει να τα ονομάζει και να τα εμφανίζει χωριστά, όχι σαν ενιαίο comparable score.
- Η evidence relevance είναι heuristic token overlap με threshold 0,3 και όχι exact page/evidence alignment.
- Τα current RAGChecker inputs έχουν `n_context_chunks=1` για όλα τα 450 examples, επειδή τα πέντε chunks έχουν συγχωνευθεί σε ένα string. Αυτό αλλοιώνει context-level retriever metrics.

Η migration πρέπει να κρατήσει δύο διακριτές έννοιες:

- `research_legacy_v1`: immutable historical snapshot με τεκμηριωμένους περιορισμούς,
- `platform_v1`: διορθωμένο, versioned comparison protocol με κοινό corpus/query snapshot, explicit candidate counts και ίδιες preprocessing επιλογές.

### 6.3 Metadata και citations χάνονται

- Και τα 37.037 stored chunks έχουν null `company`, `doc_type` και `doc_period`, παρότι αυτά υπήρχαν νωρίτερα στο dataset.
- Δεν υπάρχουν page/section fields στα chunk/retrieval outputs.
- Τα absolute local paths αποθηκεύονται σε chunks και manifests και εκθέτουν workstation metadata.
- Τα chunk lengths φτάνουν τους 9.079 χαρακτήρες παρότι η δηλωμένη τιμή είναι 1.500, πιθανότατα λόγω παλαιότερης table-preservation λογικής που δεν υπάρχει πλέον στο source.
- 81 από 84 documents έχουν gaps στα `chunk_index`, επειδή μικρά chunks φιλτράρονται μετά το split. Αυτό δεν είναι απαραίτητα λάθος, αλλά χρειάζεται ξεχωριστό stable ordinal και source span.

## 7. Production-readiness gaps

### Public repository και governance

- no Git history, README, software license, citation, contribution/security policy,
- no ignore policy για `.env`, uploads, PDFs, parsed text, embeddings, DB volumes και model caches,
- προσωπικά absolute paths σε notebooks και data artifacts,
- unresolved publication decision για unchanged notebook outputs,
- benchmark license είναι non-commercial και πρέπει να διαχωριστεί από τη software license,
- κανένα checksum/provenance record για downloaded documents.

### Configuration και packaging

- no Python 3.12-enforced package,
- no pinned dependency groups ή lock strategy,
- duplicated constants/paths/functions στα notebooks,
- no Pydantic v2 settings, environment validation ή startup checks,
- no versioned retrieval/generation/evaluation configs.

### Persistence και data model

- FAISS/NPY/CSV/Pickle είναι local research storage, όχι transactional application state,
- no PostgreSQL/pgvector, migrations, repository layer, deduplication ή lifecycle status,
- no entity model για document, page/section, chunk, embedding, query, retrieval run, answer/citation και evaluation run,
- no retention/deletion policy για uploaded documents.

### Ingestion

- no upload MIME/magic-byte/size/page validation,
- no content hashing, idempotency ή duplicate detection,
- no durable background job, retry policy ή partial-failure handling,
- no structured page/section provenance,
- no parser/chunker version recorded per artifact.

### Retrieval

- in-memory global FAISS και O(corpus) Python BM25 scan,
- no document-selection filters or tenant/user scope,
- no cache invalidation/corpus revision semantics,
- no latency, candidate-count ή model-revision trace,
- no controlled comparison protocol.

Για το μικρό portfolio scope, το προτεινόμενο BM25 είναι explicit Python implementation πάνω σε cached corpus statistics keyed από corpus revision και selected document IDs, με chunks sourced από PostgreSQL. Αυτό κρατά την ακριβή BM25/RRF ερευνητική λογική χωρίς να βαφτίζει το PostgreSQL full-text rank ως BM25. Ο περιορισμός single-process cache θα τεκμηριωθεί. Μελλοντικό horizontal scaling θα απαιτήσει shared lexical index/search engine και δεν θα παρουσιαστεί ως ήδη λυμένο.

### Generation και citations

- no typed/structured answer contract,
- citations εμφανίζονται μόνο μέσα σε concatenated context labels και όχι ως validated output,
- no token budgeting, provider timeout/retry classification, usage/cost metadata ή cancellation,
- no validation ότι citation IDs ανήκουν στα supplied chunks,
- no prompt-injection handling ή disclaimer ότι το demo δεν παρέχει επενδυτική συμβουλή.

### API, UI και jobs

- no FastAPI endpoints, versioning, OpenAPI contract, pagination ή readiness checks,
- no long-running ingestion/evaluation worker,
- no Streamlit client/backend boundary,
- no auth/rate limits. Για local recruiter demo μπορεί να τεκμηριωθεί ότι το MVP είναι single-user/local. Public hosting θα απαιτεί auth, quotas, encrypted object storage και abuse controls πριν θεωρηθεί ασφαλές.

### Tests, observability και delivery

- no unit/integration/API tests,
- no fake OpenAI provider και no guarantee ότι tests δεν κάνουν network calls,
- no ruff, mypy, coverage gates ή pre-commit,
- no structured JSON logging, request/job correlation IDs, health/readiness ή clear exception taxonomy,
- no Docker/Compose, Alembic, CI ή deployment documentation.

### Evaluation integrity

- deterministic metrics είναι duplicated και με διαφορετικά thresholds,
- evaluator failures/skips γράφονται ως numeric zero αντί `null` + status,
- RAGAS/RAGChecker runs δεν κρατούν πλήρες model/package/prompt provenance,
- ένα ξεχωριστό `eval_results/` περιέχει 20-query judge outputs χωρίς αντίστοιχο current notebook/source workflow,
- no paired-run validation ότι όλα τα modes αξιολογήθηκαν στα ίδια query IDs,
- no confidence intervals ή explicit statement ότι τα 150 examples είναι μικρό benchmark sample.

## 8. Προτεινόμενο product contract

### Core API

- `POST /api/v1/documents`: PDF upload, επιστρέφει document και ingestion job IDs.
- `GET /api/v1/documents`: list/select documents με status και metadata.
- `GET /api/v1/documents/{document_id}`: document details και ingestion summary.
- `GET /api/v1/jobs/{job_id}`: durable job status/error/progress.
- `POST /api/v1/queries`: question, selected document IDs, retrieval mode, top-k και optional query expansion.
- `GET /api/v1/queries/{query_id}`: answer, citations, retrieved chunks και run metadata.
- `POST /api/v1/evaluations`: FinanceBench-like JSONL/JSON benchmark και selected modes.
- `GET /api/v1/evaluations/{evaluation_id}`: status, aggregate/per-query metrics και failures.
- `GET /health/live` και `GET /health/ready`.

Το query response πρέπει να επιστρέφει τουλάχιστον:

- grounded answer ή explicit abstention,
- validated citation IDs,
- `document_id`, display filename, page range και section path ανά citation,
- retrieved chunk text/preview και rank,
- ξεχωριστά `dense_score`, `bm25_score`, `rrf_score`, `rerank_score` όπου εφαρμόζονται,
- mode, model/config versions, latency και corpus revision.

### Ελάχιστο database model

- `documents`, `document_versions`, `ingestion_jobs`,
- `document_elements` ή page-aware intermediate records,
- `chunks` με pgvector embedding και provenance,
- `queries`, `retrieval_runs`, `retrieval_results`,
- `answers`, `answer_citations`,
- `evaluation_datasets`, `evaluation_runs`, `evaluation_items`, `evaluation_metrics`.

## 9. Phased implementation plan

Κάθε φάση είναι approval gate. Μετά από κάθε φάση θα παραδίδονται: σύντομη περιγραφή αλλαγών, μόνο το συμφωνημένο scope, αποτελέσματα checks και οι ακριβείς εντολές που πράγματι εκτελέστηκαν. Δεν θα ξεκινά η επόμενη φάση χωρίς έγκριση.

### Φάση 0 — Public-repository boundary και project foundation

Scope:

- οριστικοποίηση ονόματος/package `financial-rag-platform` / `financial_rag`,
- `.gitignore`, `.gitattributes`, `.env.example` χωρίς secret values,
- data/publication policy, `DATA_LICENSE.md`, FinanceBench citation και software-license decision,
- `README.md`, `pyproject.toml`, Python 3.12 constraint, dependency groups,
- skeleton directories χωρίς business implementation,
- ruff, mypy, pytest, coverage και pre-commit configuration,
- unchanged notebooks παραμένουν στο `notebooks/` με `notebooks/README.md` που τα χαρακτηρίζει research-only,
- explicit publication gate για notebook outputs και absolute-path disclosure.

Exit criteria:

- `git status` δεν προτείνει raw/derived data ή `.env` για commit,
- clean install σε Python 3.12,
- lint/type/test commands τρέχουν σε empty skeleton,
- κανένα literal secret ή private source file στο staged/public set.

Προβλεπόμενες local εντολές σε PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\pre-commit.exe run --all-files
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe -q
```

### Φάση 1 — Domain contracts, settings, logging και PostgreSQL foundation

Scope:

- Pydantic v2 request/response/domain schemas,
- `pydantic-settings` με `.env` loading και startup validation,
- structured JSON logs, correlation IDs και typed exception hierarchy,
- SQLAlchemy 2.0 async models/repositories,
- PostgreSQL + pgvector Docker Compose service,
- initial Alembic migration για documents/jobs/chunks,
- unit και database integration tests.

Exit criteria:

- migration up/down σε clean database,
- pgvector extension και 1.024-dimensional vector column validated,
- settings fail clearly όταν λείπει required non-secret config,
- logs δεν περιέχουν document content ή secrets.

```powershell
Copy-Item .env.example .env
docker compose up -d db
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\pytest.exe tests\unit\core tests\integration\db -q
.\.venv\Scripts\alembic.exe downgrade base
.\.venv\Scripts\alembic.exe upgrade head
docker compose down
```

### Φάση 2 — Secure ingestion και provenance-aware chunking

Scope:

- PDF validation, content hash, safe filename και deduplication,
- Docling parser adapter,
- versioned cleaner,
- structured element/page/section-aware chunker,
- durable PostgreSQL-backed worker queue με job states και retryable/non-retryable errors,
- document/chunk persistence χωρίς embeddings ακόμη,
- synthetic PDF fixtures και mocked parser unit tests όπου είναι κατάλληλο.

Exit criteria:

- idempotent re-upload,
- invalid/oversized/non-PDF files απορρίπτονται,
- κάθε persisted chunk έχει stable ID, document version, page range, section path και transform versions,
- partial parse failure δεν αφήνει “ready” document.

```powershell
docker compose up -d db api worker
Invoke-RestMethod http://localhost:8000/health/ready
.\.venv\Scripts\pytest.exe tests\unit\ingestion tests\integration\ingestion -q
docker compose logs --no-color api worker
docker compose down
```

### Φάση 3 — Embeddings και reproducible retrieval modes

Scope:

- embedding provider interface και BGE-M3 adapter,
- pgvector indexing/search με explicit cosine semantics,
- exact, transparent BM25 service με corpus-revision cache,
- RRF service με versioned weights,
- reranker adapter με batching,
- optional finance query expansion ως ανεξάρτητη config dimension,
- modes `dense`, `hybrid`, `hybrid_reranked`, κοινό result schema και score traces,
- corrected `platform_v1` comparison config και immutable `research_legacy_v1` metadata record.

Exit criteria:

- deterministic tests για BM25/RRF/ranking/tie-breaking,
- ίδια query/corpus/preprocessing snapshot σε paired comparisons,
- reranker λαμβάνει το δηλωμένο candidate pool, όχι truncated top-10,
- no model download ή external call στα automated tests.

```powershell
docker compose up -d db
.\.venv\Scripts\pytest.exe tests\unit\retrieval tests\integration\retrieval -q
.\.venv\Scripts\python.exe -m financial_rag.cli evaluate-retrieval --config configs\evaluation\platform_v1.yaml --fixture tests\fixtures\benchmark.jsonl
docker compose down
```

### Φάση 4 — Grounded generation, citations και FastAPI query API

Scope:

- explicit prompt builder και context token budget,
- `AnswerGenerator` interface,
- official OpenAI/LangChain OpenAI adapter με model από settings,
- typed structured answer (`answer`, `abstained`, `citation_ids`),
- citation validation απέναντι μόνο στα supplied chunks,
- provider timeout/retry/error mapping και usage metadata,
- document/query/job endpoints και OpenAPI examples.

Exit criteria:

- API επιστρέφει answer + validated page/section citations + retrieved chunks/scores,
- invalid citation IDs απορρίπτονται ή μετατρέπονται σε abstention/error,
- tests χρησιμοποιούν fake generator· καμία live OpenAI κλήση σε `pytest` ή CI,
- missing `OPENAI_API_KEY` επηρεάζει μόνο generation readiness και όχι import/test collection.

```powershell
docker compose up -d db api worker
.\.venv\Scripts\pytest.exe tests\unit\generation tests\api -q
Invoke-RestMethod http://localhost:8000/openapi.json | Out-Null
Invoke-RestMethod http://localhost:8000/health/ready
docker compose down
```

### Φάση 5 — Recruiter-friendly Streamlit client

Scope:

- upload/select document flow,
- question form και retrieval mode selector,
- grounded answer με clickable citation panels,
- expandable retrieved chunks με rank, component scores, document, page και section,
- side-by-side mode comparison,
- clear job/error/empty states,
- το Streamlit app επικοινωνεί μόνο μέσω FastAPI, όχι απευθείας με DB/models.

Exit criteria:

- demo flow upload → indexed → question → citations,
- compare view δείχνει καθαρά διαφορετικά score types,
- no API key στο browser/UI state ή logs.

```powershell
docker compose up --build -d db api worker
.\.venv\Scripts\pytest.exe tests\unit\ui tests\api -q
.\.venv\Scripts\streamlit.exe run apps\streamlit_app.py
docker compose down
```

### Φάση 6 — FinanceBench-like evaluation subsystem

Scope:

- versioned benchmark schema/importer χωρίς bundled private/source documents,
- paired execution των τριών retrieval modes,
- Hit@K και MRR με explicit relevance definition,
- deterministic answer metrics και failure taxonomy σε μία canonical implementation,
- optional RAGAS/RAGChecker adapters με `completed/skipped/failed` status και null metrics όταν δεν εκτελούνται,
- run manifests, config/corpus hashes, per-query exports και comparison report,
- API/CLI/Streamlit evaluation view.

Exit criteria:

- query-set equality assertion πριν από comparisons,
- historical και corrected results δεν overwrite-άρονται,
- failed/skipped evaluator δεν εμφανίζεται ως score 0,
- retrieval benchmark τρέχει offline· answer tests χρησιμοποιούν checked-in synthetic/precomputed fixtures.

```powershell
docker compose up -d db api worker
.\.venv\Scripts\pytest.exe tests\unit\evaluation tests\integration\evaluation -q
.\.venv\Scripts\python.exe -m financial_rag.cli evaluate-retrieval --config configs\evaluation\platform_v1.yaml --fixture tests\fixtures\benchmark.jsonl
.\.venv\Scripts\python.exe -m financial_rag.cli evaluation-report --latest
docker compose down
```

### Φάση 7 — CI, containers, documentation και public release gate

Scope:

- final API/worker/Streamlit Dockerfiles και Compose profiles,
- GitHub Actions για Python 3.12, lint, types, tests, coverage και container build,
- PostgreSQL/pgvector CI service,
- architecture, API, evaluation methodology, limitations, security/data policy και demo documentation,
- sanitized screenshots μόνο από synthetic/publicly-cleared documents,
- final staged-file, secret, license και large-file audit.

Exit criteria:

- reproducible `docker compose up --build`,
- CI green χωρίς OpenAI secret,
- coverage threshold συμφωνημένο από πραγματική baseline και όχι αυθαίρετο claim,
- README δεν χρησιμοποιεί “production-ready” ή performance claims πέρα από όσα αποδεικνύουν τα checks,
- public commit set δεν περιέχει `.env`, source PDFs, derived full text, embeddings, DB volumes ή uncleared outputs.

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe --cov=financial_rag --cov-report=term-missing --cov-report=xml
.\.venv\Scripts\pre-commit.exe run --all-files
docker compose config
docker compose build
git status --short
```

## 10. Προτεινόμενες αποφάσεις για έγκριση

Προτείνω να εγκριθούν τα εξής defaults πριν αρχίσει η Φάση 0:

1. **Data policy:** κανένα PDF, parsed/cleaned full text, embedding, FAISS index, QA context dump ή local DB volume στο public Git. Μόνο official downloader/importer, attribution και synthetic fixtures.
2. **Notebook policy:** τα 15 notebooks παραμένουν byte-for-byte αμετάβλητα. Πριν δημοσιευθούν, γίνεται ξεχωριστή manual αποδοχή των embedded outputs, FinanceBench excerpts και absolute local paths. Αν δεν εγκριθούν, παραμένουν local research artifacts μέχρι να λυθεί η σύγκρουση με το public-release requirement.
3. **Licensing:** ξεχωριστή software license (προτεινόμενη MIT) και `DATA_LICENSE.md` για FinanceBench CC BY-NC 4.0/attribution. Αυτό δεν είναι νομική γνωμοδότηση και δεν καλύπτει αυτόματα redistribution των source PDFs.
4. **Retrieval fidelity:** κρατάμε την exact BM25 + RRF business logic και διορθώνουμε το reranker candidate-pool bug σε νέο `platform_v1`. Τα σημερινά αποτελέσματα μένουν ως `research_legacy_v1` με caveats.
5. **Architecture:** explicit services/protocols, PostgreSQL + pgvector και μικρός PostgreSQL-backed worker. LangChain μόνο ως adapter/tooling, χωρίς opaque chains.
6. **Testing:** κανένα automated test ή CI workflow δεν κάνει live OpenAI call ή κατεβάζει μεγάλα models. Live evaluation είναι ξεχωριστή, ρητά ενεργοποιούμενη local διαδικασία.
7. **Scope honesty:** local single-user recruiter demo πρώτα. Authentication, distributed lexical index, autoscaling και managed object storage τεκμηριώνονται ως future deployment requirements και όχι ως ήδη υλοποιημένες δυνατότητες.

Με την έγκριση αυτών των επτά αποφάσεων μπορεί να ξεκινήσει μόνο η Φάση 0. Η ingestion/retrieval/API implementation δεν πρέπει να αρχίσει στο ίδιο βήμα.
