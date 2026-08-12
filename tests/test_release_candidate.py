"""Offline tests for the release-candidate source contract."""

import json
from dataclasses import asdict
from pathlib import Path

from scripts.check_release_candidate import (
    infrastructure_observations,
    notebook_inventory_is_valid,
    source_contract_checks,
)

PROJECT_ROOT = Path(__file__).parents[1]
CONTRACT_PATH = PROJECT_ROOT / "configs" / "release" / "platform_rc_v1.json"


def test_checked_in_release_candidate_contract_matches_source() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    checks = source_contract_checks(PROJECT_ROOT, contract)

    assert checks
    assert {check.state for check in checks} == {"passed"}


def test_infrastructure_preflight_never_exposes_environment_values() -> None:
    serialized = json.dumps([asdict(check) for check in infrastructure_observations()])

    assert "postgresql://" not in serialized
    assert "postgresql+asyncpg://" not in serialized


def test_notebook_inventory_allows_only_public_or_complete_local_state() -> None:
    assert notebook_inventory_is_valid(0, 15)
    assert notebook_inventory_is_valid(15, 15)
    assert not notebook_inventory_is_valid(14, 15)
