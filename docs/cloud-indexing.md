# Local and cloud-GPU indexing

## What runs locally without a GPU

The normal development install includes NumPy and `faiss-cpu`. It supports:

- every unit test with deterministic `FakeEmbeddingProvider` and
  `FakeReranker`;
- FAISS `IndexFlatIP` build/search over synthetic or caller-supplied vectors;
- BM25, weighted RRF, query expansion, manifests, and local artifact save/load;
- explicit BGE adapter construction without importing or loading a model.

Install and verify the offline path:

```powershell
py -3.12 -m pip install -e ".[dev]"
.\.venv\Scripts\pytest.exe tests\unit\retrieval -q
```

No test downloads model weights, requires a Hugging Face login, calls OpenAI,
uses a GPU, or indexes the real FinanceBench corpus.

## Optional model installation

FlagEmbedding is intentionally outside runtime/dev requirements used by CI:

```powershell
py -3.12 -m pip install -e ".[models]"
```

The optional extra provides the lazy `BgeM3EmbeddingProvider` and
`BgeM3Reranker` runtime dependency. Model weights are still not bundled. The
first explicit encode/score call may resolve weights through the environment's
configured model cache or model hub, so it must be treated as an opt-in local or
cloud operation—not an automated test.

For a deliberately small CPU experiment, construct providers with explicit
settings:

```python
from financial_rag.retrieval import BgeM3EmbeddingProvider, BgeM3Reranker

embedder = BgeM3EmbeddingProvider(device="cpu", batch_size=4, use_fp16=False)
reranker = BgeM3Reranker(device="cpu", batch_size=4, use_fp16=False)
```

Full-corpus BGE-M3 embedding and repeated cross-encoder reranking may be slow and
memory-intensive on CPU. The retrieval implementation makes no local throughput claim.

## Cloud GPU execution

Use a private Kaggle/Colab runtime or another authorized GPU environment for a
full corpus run:

1. Copy only the project code and obtain source data through an authorized,
   non-public process.
2. Install the project with `.[models]` in an environment whose PyTorch/CUDA
   versions are compatible with the selected GPU.
3. Load `configs/retrieval/platform_v1.json`.
4. Recreate ingestion chunks from local/private documents.
5. Construct `BgeM3EmbeddingProvider(device="cuda", batch_size=<measured size>)`.
6. Build the retrieval service with the exact ingestion chunking fingerprint.
7. Save artifacts beneath an ignored path such as
   `data/processed/retrieval_index/platform_v1/`.
8. Validate a reload before using the index for retrieval.

Batch size is deliberately explicit because safe values depend on GPU memory,
document lengths, and installed model/runtime versions. `device="auto"` delegates
selection to FlagEmbedding; `cpu` and `cuda` make intent explicit.

## Artifact boundary

The generated FAISS file, chunk mapping, JSON manifest, embeddings, model cache,
and any full-corpus retrieval output must not be committed or attached to a
GitHub release. The repository ignores `.faiss`, `*.retrieval.json*`, data
processing directories, caches, embeddings, and index formats. Before sharing
code, run the publication checks in `docs/publication-policy.md`.

The chunk mapping contains full chunk text and is subject to the same prohibition
as parsed documents and generated contexts. Keep cloud outputs private and move
them only through an approved private channel if a later local run needs them.

## Index compatibility rule

An embedding model change always requires a new index. The same applies to a
dimension change, a different normalization method, or a different ingestion
chunking fingerprint. The loader raises `ManifestCompatibilityError`; it does
not coerce, pad, truncate, or silently reuse incompatible vectors.

Full corpus indexing and real reranker execution are explicit manual/cloud work.
They are not performed by the retrieval implementation, pytest, pre-commit, or CI.
