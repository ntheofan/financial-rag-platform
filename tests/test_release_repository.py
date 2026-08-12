"""Offline tests for notebook immutability and release repository checks."""

import hashlib
from pathlib import Path

from scripts.check_release_repository import verify_notebook_hashes


def _write_snapshot(root: Path, *, changed: bool = False) -> Path:
    notebooks = root / "notebooks"
    notebooks.mkdir()
    lines: list[str] = []
    for index in range(1, 16):
        name = f"{index:02d}_synthetic.ipynb"
        content = f"synthetic notebook {index}".encode()
        (notebooks / name).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        lines.append(f"{digest}  {name}")
    if changed:
        (notebooks / "15_synthetic.ipynb").write_bytes(b"changed")
    manifest = root / "notebook_hashes_v1.sha256"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def test_notebook_hash_snapshot_accepts_exact_inventory(tmp_path: Path) -> None:
    result = verify_notebook_hashes(tmp_path, _write_snapshot(tmp_path))

    assert result.state == "passed"


def test_notebook_hash_snapshot_rejects_content_change(tmp_path: Path) -> None:
    result = verify_notebook_hashes(tmp_path, _write_snapshot(tmp_path, changed=True))

    assert result.state == "failed"
    assert result.detail == "a notebook hash changed"


def test_notebook_hash_snapshot_allows_public_clone_without_artifacts(tmp_path: Path) -> None:
    manifest = _write_snapshot(tmp_path)
    for notebook in (tmp_path / "notebooks").glob("*.ipynb"):
        notebook.unlink()

    result = verify_notebook_hashes(tmp_path, manifest)

    assert result.state == "passed"
    assert result.detail.startswith("public clone")
