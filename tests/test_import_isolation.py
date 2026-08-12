"""Subprocess proof that lightweight adapters do not import model/provider stacks."""

import os
import subprocess
import sys
from pathlib import Path


def test_demo_client_import_does_not_load_models_or_provider_sdk() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    code = """
import sys
import financial_rag.api.schemas
import financial_rag.demo.client
blocked = {'torch', 'FlagEmbedding', 'openai'} & set(sys.modules)
if blocked:
    raise SystemExit(','.join(sorted(blocked)))
"""

    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(source_root)},
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
