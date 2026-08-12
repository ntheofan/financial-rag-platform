"""Fail when a prospective public commit contains restricted local material."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_PUBLIC_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024

FORBIDDEN_SUFFIXES = frozenset(
    {
        ".arrow",
        ".7z",
        ".db",
        ".faiss",
        ".gz",
        ".index",
        ".key",
        ".npy",
        ".npz",
        ".parquet",
        ".pdf",
        ".pem",
        ".pickle",
        ".pkl",
        ".rar",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".tgz",
        ".zip",
    }
)
FORBIDDEN_ROOTS = frozenset(
    {
        ".cache",
        ".huggingface",
        ".postgres",
        "artifacts",
        "evaluation-runs",
        "huggingface",
        "model-cache",
        "models",
        "outputs",
        "pgdata",
        "uploads",
    }
)
ALLOWED_DATA_FILES = frozenset(
    {
        "data/raw/.gitkeep",
        "data/interim/.gitkeep",
        "data/processed/.gitkeep",
    }
)


@dataclass(frozen=True, slots=True)
class PublicationViolation:
    """One safe, content-free reason a path cannot cross the public boundary."""

    path: str
    reason: str


def _secret_patterns() -> tuple[re.Pattern[str], ...]:
    """Build patterns in pieces so this scanner does not flag its own source."""
    openai_prefix = "sk" + r"-[A-Za-z0-9_-]{16,}"
    github_prefix = "gh" + r"[oprsu]_[A-Za-z0-9]{20,}"
    aws_prefix = "AK" + r"IA[0-9A-Z]{16}"
    private_key_header = "BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"
    username = r"[A-Za-z0-9._-]+"
    windows_home = r"[A-Za-z]:\\" + "Users" + rf"\\{username}"
    posix_home = "/" + "home" + rf"/{username}"
    return tuple(
        re.compile(pattern)
        for pattern in (
            openai_prefix,
            github_prefix,
            aws_prefix,
            private_key_header,
            windows_home,
            posix_home,
        )
    )


def _public_name(path: Path) -> str:
    return path.as_posix().removeprefix("./")


def inspect_candidate(root: Path, relative_path: Path) -> list[PublicationViolation]:
    """Inspect one Git candidate without logging file content."""
    name = _public_name(relative_path)
    parts = relative_path.parts
    violations: list[PublicationViolation] = []

    if not parts:
        return violations
    if parts[0] in FORBIDDEN_ROOTS:
        violations.append(PublicationViolation(name, "restricted runtime/data directory"))
    if parts[0] == "benchmarks" and len(parts) > 1 and parts[1] == "local":
        violations.append(PublicationViolation(name, "restricted local benchmark directory"))
    if parts[0] == "data" and name not in ALLOWED_DATA_FILES:
        violations.append(PublicationViolation(name, "research data is not publishable"))
    if parts[0] == "notebooks" and relative_path.suffix.lower() == ".ipynb":
        violations.append(PublicationViolation(name, "notebook publication requires manual review"))

    filename = relative_path.name.lower()
    if "financebench" in filename and relative_path.suffix.lower() != ".md":
        violations.append(PublicationViolation(name, "FinanceBench artifact is not publishable"))
    if filename == ".env" or (filename.startswith(".env.") and filename != ".env.example"):
        violations.append(PublicationViolation(name, "secret-bearing environment file"))
    if relative_path.suffix.lower() in FORBIDDEN_SUFFIXES and not (
        relative_path.suffix.lower() == ".pdf" and name.startswith("tests/fixtures/")
    ):
        violations.append(PublicationViolation(name, "restricted binary or derived artifact type"))

    absolute_path = root / relative_path
    if absolute_path.is_symlink():
        violations.append(PublicationViolation(name, "symbolic links require manual review"))
        return violations
    try:
        size = absolute_path.stat().st_size
    except OSError:
        return [PublicationViolation(name, "candidate cannot be read")]
    if size > MAX_PUBLIC_FILE_BYTES:
        violations.append(PublicationViolation(name, "file exceeds the 10 MiB public limit"))
        return violations
    if size > MAX_TEXT_SCAN_BYTES:
        return violations

    try:
        raw = absolute_path.read_bytes()
    except OSError:
        return [PublicationViolation(name, "candidate cannot be read")]
    if b"\x00" in raw:
        return violations
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return violations
    if any(pattern.search(text) for pattern in _secret_patterns()):
        violations.append(PublicationViolation(name, "credential or local absolute path pattern"))
    return violations


def git_candidates(root: Path) -> tuple[Path, ...]:
    """Return tracked and non-ignored untracked files from Git, deterministically."""
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("Unable to enumerate the Git publication candidates.")
    names = completed.stdout.decode("utf-8").split("\0")
    return tuple(sorted((Path(name) for name in names if name), key=_public_name))


def inspect_repository(root: Path) -> tuple[PublicationViolation, ...]:
    """Inspect every tracked or non-ignored file at the public boundary."""
    violations: list[PublicationViolation] = []
    for candidate in git_candidates(root):
        violations.extend(inspect_candidate(root, candidate))
    return tuple(violations)


def main() -> int:
    """Run the publication gate and emit filenames plus safe reason codes only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Git worktree root")
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        violations = inspect_repository(root)
    except RuntimeError as exc:
        print(f"publication gate failed: {exc}")
        return 2
    if violations:
        print("publication gate failed:")
        for violation in violations:
            print(f"- {violation.path}: {violation.reason}")
        return 1
    print(f"publication gate passed: {len(git_candidates(root))} candidate files inspected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
