"""Validate the checked-in Phase 10 release-candidate source contract."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from financial_rag import __version__
from financial_rag.api.app import create_app
from financial_rag.api.settings import ApiSettings

CheckState = Literal["passed", "failed", "unavailable"]
REQUIRED_SOURCE_CHECKS = (
    "publication",
    "ruff_lint",
    "ruff_format",
    "mypy",
    "pytest_coverage",
    "alembic_head",
    "openapi_contract",
    "synthetic_end_to_end",
    "import_isolation",
    "release_repository",
)
REQUIRED_INFRASTRUCTURE_CHECKS = (
    "postgres_pgvector_migrations",
    "model_enabled_index_build",
    "compose_runtime",
    "real_local_acceptance",
    "dependency_audit",
    "github_actions",
)


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    """One content-free release-candidate check result."""

    name: str
    state: CheckState
    detail: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load release contract: {path.as_posix()}") from exc
    if not isinstance(value, dict):
        raise ValueError("Release contract must be a JSON object.")
    return value


def _protocol_value(path: Path, key: str) -> str | None:
    value = _load_json(path).get(key)
    return value if isinstance(value, str) else None


def _migration_heads(root: Path) -> tuple[str, ...]:
    revisions: dict[str, str | None] = {}
    for path in sorted((root / "migrations" / "versions").glob("*.py")):
        assignments: dict[str, Any] = {}
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in tree.body:
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if node.target.id not in {"revision", "down_revision"} or node.value is None:
                continue
            assignments[node.target.id] = ast.literal_eval(node.value)
        revision = assignments.get("revision")
        down_revision = assignments.get("down_revision")
        if isinstance(revision, str) and (down_revision is None or isinstance(down_revision, str)):
            revisions[revision] = down_revision
    parents = {parent for parent in revisions.values() if parent is not None}
    return tuple(sorted(set(revisions) - parents))


def notebook_inventory_is_valid(discovered: int, expected_local: object) -> bool:
    """Accept only a public clone with zero artifacts or the complete local inventory."""
    return isinstance(expected_local, int) and discovered in {0, expected_local}


def source_contract_checks(root: Path, contract: dict[str, Any]) -> tuple[PreflightCheck, ...]:
    """Check deterministic source contracts without external services or secrets."""
    expected_python = str(contract.get("python_minimum", ""))
    current_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    try:
        minimum_python = tuple(int(part) for part in expected_python.split("."))
    except ValueError:
        minimum_python = ()
    python_supported = (sys.version_info.major, sys.version_info.minor) >= minimum_python and bool(
        minimum_python
    )
    protocols = contract.get("protocols")
    protocol_map = protocols if isinstance(protocols, dict) else {}
    expected_paths = contract.get("api_paths")
    actual_paths = sorted(
        create_app(settings=ApiSettings.model_validate({})).openapi().get("paths", {}).keys()
    )
    notebooks = tuple(sorted((root / "notebooks").glob("*.ipynb")))
    expected_notebooks = contract.get("notebook_count")
    expected_head = contract.get("alembic_head")
    heads = _migration_heads(root)

    values = (
        (
            "python_version",
            python_supported,
            f"Python {current_python}; contract minimum is {expected_python}",
        ),
        (
            "release_schema",
            contract.get("schema_version") == "platform_rc_v1",
            "release contract uses platform_rc_v1",
        ),
        (
            "gate_inventory",
            tuple(contract.get("required_source_checks", ())) == REQUIRED_SOURCE_CHECKS
            and tuple(contract.get("required_infrastructure_checks", ()))
            == REQUIRED_INFRASTRUCTURE_CHECKS,
            "source and infrastructure gate inventories are complete",
        ),
        (
            "package_version",
            __version__ == contract.get("package_version"),
            "package and release-contract versions agree",
        ),
        (
            "project_status",
            contract.get("project_status") == "in_development",
            "public status remains in_development",
        ),
        (
            "retrieval_protocol",
            _protocol_value(root / "configs/retrieval/platform_v1.json", "platform_version")
            == protocol_map.get("retrieval"),
            "retrieval protocol matches the release contract",
        ),
        (
            "evaluation_protocol",
            _protocol_value(root / "configs/evaluation/platform_eval_v1.json", "protocol_version")
            == protocol_map.get("evaluation"),
            "evaluation protocol matches the release contract",
        ),
        (
            "runtime_protocol",
            _protocol_value(root / "configs/runtime/local_v1.json", "runtime_version")
            == protocol_map.get("runtime"),
            "runtime protocol matches the release contract",
        ),
        (
            "alembic_head",
            heads == (expected_head,),
            f"discovered migration heads: {', '.join(heads) or 'none'}",
        ),
        (
            "openapi_paths",
            isinstance(expected_paths, list) and actual_paths == sorted(expected_paths),
            f"discovered {len(actual_paths)} API paths",
        ),
        (
            "notebook_inventory",
            notebook_inventory_is_valid(len(notebooks), expected_notebooks),
            (
                f"discovered {len(notebooks)} local notebooks; contents were not read"
                if notebooks
                else "public clone contains no ignored notebook artifacts"
            ),
        ),
    )
    return tuple(
        PreflightCheck(name=name, state="passed" if passed else "failed", detail=detail)
        for name, passed, detail in values
    )


def infrastructure_observations() -> tuple[PreflightCheck, ...]:
    """Report local capability presence without connecting or exposing values."""
    checks = (
        ("docker_cli", shutil.which("docker") is not None, "Docker CLI is available"),
        (
            "database_configuration",
            bool(os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")),
            "a database URL is configured",
        ),
        (
            "model_adapter_package",
            importlib.util.find_spec("FlagEmbedding") is not None,
            "the optional FlagEmbedding package is discoverable",
        ),
    )
    return tuple(
        PreflightCheck(
            name=name,
            state="passed" if available else "unavailable",
            detail=detail if available else detail.replace(" is ", " is not "),
        )
        for name, available, detail in checks
    )


def main() -> int:
    """Emit safe JSON and fail only on source drift unless infrastructure is required."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--require-infrastructure",
        action="store_true",
        help="also fail when Docker/database/model prerequisites are unavailable",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    contract_path = root / "configs" / "release" / "platform_rc_v1.json"
    try:
        contract = _load_json(contract_path)
        source = source_contract_checks(root, contract)
    except (OSError, ValueError) as exc:
        print(json.dumps({"schema_version": "platform_rc_v1", "error": str(exc)}))
        return 2
    infrastructure = infrastructure_observations()
    checks = source + infrastructure
    print(
        json.dumps(
            {
                "schema_version": contract.get("schema_version"),
                "checks": [asdict(check) for check in checks],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if any(check.state == "failed" for check in source):
        return 1
    if args.require_infrastructure and any(check.state != "passed" for check in infrastructure):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
