# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS foundation

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

# Install dependency layers from stable project metadata and a minimal package.
# Full source is copied only into the final targets, so ordinary code changes do
# not force the heavyweight model dependency layer to resolve again.
COPY pyproject.toml README.md LICENSE DATA_LICENSE.md ./
COPY src/financial_rag/__init__.py src/financial_rag/py.typed ./src/financial_rag/


FROM foundation AS api-dependencies

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install ".[api]"


FROM api-dependencies AS api

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-deps . \
    && install -d -o 10001 -g 10001 /var/cache/financial-rag/huggingface

COPY alembic.ini ./
COPY migrations ./migrations
COPY configs ./configs

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "financial_rag.runtime.app:create_local_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]


FROM api-dependencies AS api-model-dependencies

ARG PYTORCH_VERSION=2.9.1
ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install "torch==${PYTORCH_VERSION}" --index-url "${PYTORCH_CPU_INDEX_URL}" \
    && python -m pip install ".[models]"


FROM api-model-dependencies AS api-models

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-deps . \
    && install -d -o 10001 -g 10001 /var/cache/financial-rag/huggingface

COPY alembic.ini ./
COPY migrations ./migrations
COPY configs ./configs

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "financial_rag.runtime.app:create_local_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]


FROM foundation AS demo-dependencies

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install ".[demo]"


FROM demo-dependencies AS demo

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --no-deps .

COPY apps ./apps

USER 10001:10001
EXPOSE 8501

CMD ["streamlit", "run", "apps/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
