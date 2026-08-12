"""Static, Docker-free checks for the local container publication boundary."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_docker_context_excludes_restricted_artifacts() -> None:
    patterns = set((PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    required = {
        ".env",
        "data",
        "notebooks",
        "artifacts",
        "evaluation-runs",
        "model-cache",
        "**/*.pdf",
        "**/*.faiss",
        "**/*.sqlite3",
    }
    assert required <= patterns


def test_images_run_as_non_root_and_keep_models_separate() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM api-model-dependencies AS api-models" in dockerfile
    assert "FROM demo-dependencies AS demo" in dockerfile
    assert dockerfile.count("USER 10001:10001") == 3
    assert (
        dockerfile.count("install -d -o 10001 -g 10001 /var/cache/financial-rag/huggingface") == 2
    )
    assert "COPY data" not in dockerfile
    assert "COPY notebooks" not in dockerfile


def test_model_image_uses_pinned_official_cpu_torch_and_cached_dependencies() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG PYTORCH_VERSION=2.9.1" in dockerfile
    assert "ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu" in dockerfile
    assert '"torch==${PYTORCH_VERSION}" --index-url "${PYTORCH_CPU_INDEX_URL}"' in dockerfile
    assert "FROM api-dependencies AS api-model-dependencies" in dockerfile
    assert dockerfile.count("--mount=type=cache,target=/root/.cache/pip") == 6
    assert dockerfile.index("FROM api-model-dependencies AS api-models") < dockerfile.index(
        "COPY src ./src", dockerfile.index("FROM api-model-dependencies AS api-models")
    )


def test_compose_pins_pgvector_and_orders_migration_before_api() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "pgvector/pgvector:0.8.2-pg17-bookworm" in compose
    assert 'command: ["python", "-m", "alembic", "upgrade", "head"]' in compose
    assert "condition: service_completed_successfully" in compose
    assert '"127.0.0.1:${API_PORT:-8000}:8000"' in compose
    assert '"127.0.0.1:${DEMO_PORT:-8501}:8501"' in compose
    assert "./artifacts:/runtime/artifacts:ro" in compose
