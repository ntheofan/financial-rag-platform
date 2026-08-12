# Local container runtime

The container layer packages the tested services for a local Docker Compose demo.
It does not add a new retrieval path or change `platform_v1` behavior.

## Services and images

| Service | Role | Persistence |
| --- | --- | --- |
| `database` | PostgreSQL 17 with pgvector 0.8.2 | named `postgres-data` volume |
| `migrate` | one-shot `alembic upgrade head` | none |
| `api` | FastAPI local composition, model-enabled target | ignored artifact bind mount and model-cache volume |
| `demo` | Streamlit HTTP client | none |

The database tag is version-pinned from the
[official pgvector Docker tag list](https://github.com/pgvector/pgvector#docker).

The API receives an ephemeral `/runtime/uploads` tmpfs for document staging.
Uploaded files are never image inputs or named-volume contents and are removed
after the in-process build finishes.

The root `Dockerfile` also exposes a lightweight `api` target without the
`models` extra. CI builds both that target and the real `api-models` target.
Compose deliberately uses `api-models` for the local demo. Model weights are
not baked into either image.

The model-enabled image pins `torch 2.9.1` from the official PyTorch CPU wheel
index before resolving FlagEmbedding. The verified image reports
`torch 2.9.1+cpu`, no CUDA availability, and no installed CUDA/NVIDIA Python
distributions. Dependency stages precede the full source copy and use BuildKit
pip cache mounts, so source-only rebuilds retain the heavyweight model layer.
This Docker path is the supported CPU-only local demo package; the generic
local `models` extra is not presented as a cross-platform wheel lock.

## Start the stack

Prerequisites are Docker Engine/Desktop with Compose v2. Copy the non-secret
template only when local overrides or generation are needed:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Then open `http://127.0.0.1:8501`. FastAPI docs are available at
`http://127.0.0.1:8000/docs` while `API_DOCS_ENABLED=true`.

Inspect status and logs without printing the Compose environment:

```powershell
docker compose ps
docker compose logs api demo
```

Do not paste logs publicly without checking them against
[`publication-policy.md`](publication-policy.md).

## Enable retrieval explicitly

Place only a compatible, already-created retrieval artifact directory under the
ignored local `artifacts/` directory. In the ignored `.env`, set:

```dotenv
CONTAINER_RETRIEVAL_ARTIFACT_DIRECTORY=/runtime/artifacts
```

Restart the stack. The runtime applies the existing manifest, embedding,
dimension, chunk-mapping, and configuration compatibility checks. If the
artifact is absent or incompatible, retrieval readiness fails rather than
silently rebuilding or discovering another index.

The first model-enabled start may download BGE dependencies into the Docker
`model-cache` volume. This is a runtime cache and must never be copied into the
repository or an image.

The image pre-creates `HF_HOME` for the non-root API user. If a model-cache
volume was created by an older image, recreate that cache only after confirming
it contains no required local model state; do not copy its contents into the
repository.

## Database migrations

Compose runs the one-shot `migrate` service after PostgreSQL becomes healthy and
starts FastAPI only after the migration succeeds. FastAPI never runs migrations
implicitly. To apply the current migration again after a source update:

```powershell
docker compose run --rm migrate
```

## Stop and clean up

Stop containers while retaining database/model volumes:

```powershell
docker compose down
```

`docker compose down --volumes` permanently deletes the local database and model
cache volumes. Use it only when that loss is intended.

## Troubleshooting

- **Port already allocated:** change `POSTGRES_PORT`, `API_PORT`, or `DEMO_PORT`
  in the ignored `.env`.
- **Migration fails:** inspect `docker compose logs database migrate`; do not
  start the API against a partially migrated schema.
- **API is live but retrieval is unavailable:** this is expected when
  `CONTAINER_RETRIEVAL_ARTIFACT_DIRECTORY` is blank. Configure a compatible
  ignored artifact as described above.
- **Artifact compatibility error:** rebuild the local artifact through the
  versioned retrieval pipeline; do not edit its manifest manually.
- **Model download fails:** verify network access and available disk space for
  the named model cache. The system does not include offline model weights.
- **Unexpected GPU/CUDA packages:** rebuild the `api-models` target from this
  Dockerfile; do not replace its official CPU index with the default Linux
  PyPI Torch resolution.
- **Generation returns 503:** add a real `OPENAI_API_KEY` only to `.env`; never
  put it in Compose YAML, the image, or Streamlit configuration.
