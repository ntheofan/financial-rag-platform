"""Offline checks for the public-repository boundary."""

from pathlib import Path

from scripts.check_publication import inspect_candidate


def _reasons(root: Path, relative_path: str, content: bytes = b"synthetic") -> set[str]:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {violation.reason for violation in inspect_candidate(root, Path(relative_path))}


def test_allows_public_source_and_synthetic_fixture_pdf(tmp_path: Path) -> None:
    assert not _reasons(tmp_path, "src/example.py")
    assert not _reasons(tmp_path, "tests/fixtures/synthetic.pdf")


def test_rejects_research_data_not_gitkeep(tmp_path: Path) -> None:
    reasons = _reasons(tmp_path, "data/raw/filing.txt")
    assert "research data is not publishable" in reasons


def test_rejects_notebook_without_manual_review(tmp_path: Path) -> None:
    reasons = _reasons(tmp_path, "notebooks/research.ipynb")
    assert "notebook publication requires manual review" in reasons


def test_rejects_secret_file_and_key_pattern(tmp_path: Path) -> None:
    secret = ("sk" + "-" + "x" * 24).encode()
    reasons = _reasons(tmp_path, ".env.local", secret)
    assert "secret-bearing environment file" in reasons
    assert "credential or local absolute path pattern" in reasons


def test_rejects_derived_artifact(tmp_path: Path) -> None:
    reasons = _reasons(tmp_path, "artifacts/index.faiss")
    assert "restricted runtime/data directory" in reasons
    assert "restricted binary or derived artifact type" in reasons


def test_rejects_generated_archive(tmp_path: Path) -> None:
    reasons = _reasons(tmp_path, "docs.zip")
    assert "restricted binary or derived artifact type" in reasons


def test_rejects_financebench_artifact_outside_data(tmp_path: Path) -> None:
    reasons = _reasons(tmp_path, "benchmarks/financebench.jsonl")
    assert "FinanceBench artifact is not publishable" in reasons
