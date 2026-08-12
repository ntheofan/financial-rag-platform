"""Static portability contracts for the hosted CI workflow."""

import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pytest_temp_root_has_no_missing_parent_in_a_clean_clone() -> None:
    """The configured temp root must be creatable directly below the checkout."""
    config: dict[str, Any] = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    addopts = config["tool"]["pytest"]["ini_options"]["addopts"]

    assert "--basetemp=.pytest-tmp" in addopts
    assert ".pytest-tmp/" in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")


def test_container_ci_uses_an_explicit_current_buildx_builder() -> None:
    """The GHA cache exporter must not run through the default Docker driver."""
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "docker/setup-buildx-action@v4" in workflow
    assert workflow.count("docker/build-push-action@v7") == 3
    assert "docker/build-push-action@v6" not in workflow
