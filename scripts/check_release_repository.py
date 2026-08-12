"""Check whether the Git worktree is suitable for an exact-commit release review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path
from typing import Literal, Protocol, cast


class PublicationScanner(Protocol):
    """Narrow dynamically loaded scanner surface."""

    def inspect_repository(self, root: Path) -> tuple[object, ...]: ...


check_publication = cast(
    PublicationScanner,
    import_module("scripts.check_publication" if __package__ else "check_publication"),
)

CheckState = Literal["passed", "failed", "unavailable"]
HASH_LINE = re.compile(r"^(?P<digest>[0-9a-f]{64})  (?P<name>[^/\\]+\.ipynb)$")


@dataclass(frozen=True, slots=True)
class RepositoryCheck:
    """One content-free repository readiness result."""

    name: str
    state: CheckState
    detail: str


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
    )


def verify_notebook_hashes(root: Path, manifest_path: Path) -> RepositoryCheck:
    """Compare local notebooks to a private ignored hash snapshot when present."""
    notebooks = tuple(sorted((root / "notebooks").glob("*.ipynb")))
    if not notebooks:
        return RepositoryCheck(
            "notebook_hashes",
            "passed",
            "public clone contains no notebook artifacts",
        )
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return RepositoryCheck(
            "notebook_hashes",
            "failed",
            "local notebook hash snapshot is missing or unreadable",
        )
    expected: dict[str, str] = {}
    for line in lines:
        match = HASH_LINE.fullmatch(line)
        if match is None or match["name"] in expected:
            return RepositoryCheck("notebook_hashes", "failed", "hash manifest is invalid")
        expected[match["name"]] = match["digest"]
    if len(expected) != 15:
        return RepositoryCheck(
            "notebook_hashes", "failed", "hash manifest does not contain 15 entries"
        )
    if {path.name for path in notebooks} != set(expected):
        return RepositoryCheck(
            "notebook_hashes", "failed", "notebook inventory does not match 15-file snapshot"
        )
    for path in notebooks:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return RepositoryCheck("notebook_hashes", "failed", "a notebook is unreadable")
        if digest != expected[path.name]:
            return RepositoryCheck("notebook_hashes", "failed", "a notebook hash changed")
    return RepositoryCheck(
        "notebook_hashes", "passed", "15 notebook hashes match notebook_hashes_v1"
    )


def repository_checks(root: Path) -> tuple[RepositoryCheck, ...]:
    """Inspect Git identity, cleanliness, publication boundary, and notebook hashes."""
    head = _git(root, "rev-parse", "--verify", "HEAD")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    unstaged = _git(root, "diff", "--quiet")
    staged = _git(root, "diff", "--cached", "--quiet")
    try:
        violations = check_publication.inspect_repository(root)
        publication = RepositoryCheck(
            "publication_boundary",
            "passed" if not violations else "failed",
            f"publication scanner found {len(violations)} violations",
        )
    except RuntimeError:
        publication = RepositoryCheck(
            "publication_boundary", "unavailable", "publication candidates could not be read"
        )
    untracked_count = len([name for name in untracked.stdout.split(b"\0") if name])
    return (
        RepositoryCheck(
            "git_head",
            "passed" if head.returncode == 0 else "failed",
            "Git HEAD resolves to an exact commit"
            if head.returncode == 0
            else "Git HEAD does not resolve",
        ),
        RepositoryCheck(
            "public_files_tracked",
            "passed" if untracked.returncode == 0 and untracked_count == 0 else "failed",
            f"non-ignored untracked file count: {untracked_count}",
        ),
        RepositoryCheck(
            "unstaged_changes",
            "passed" if unstaged.returncode == 0 else "failed",
            "tracked worktree has no unstaged changes"
            if unstaged.returncode == 0
            else "tracked worktree is dirty or cannot be compared",
        ),
        RepositoryCheck(
            "staged_changes",
            "passed" if staged.returncode == 0 else "failed",
            "index has no staged changes"
            if staged.returncode == 0
            else "index is dirty or cannot be compared to HEAD",
        ),
        publication,
        verify_notebook_hashes(
            root,
            root / ".cache" / "notebook_hashes_v1.sha256",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    checks = repository_checks(args.root.resolve())
    print(
        json.dumps(
            {
                "schema_version": "release_repository_check_v1",
                "checks": [asdict(check) for check in checks],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if all(check.state == "passed" for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
