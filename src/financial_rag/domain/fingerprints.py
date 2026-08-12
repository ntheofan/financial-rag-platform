"""Canonical immutable configuration fingerprints."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationFingerprint(BaseModel):
    """A frozen SHA-256 fingerprint with an explicit algorithm label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm: Literal["sha256"] = "sha256"
    value: str = Field(pattern=r"^[0-9a-f]{64}$")


def fingerprint_payload(payload: Mapping[str, Any]) -> ConfigurationFingerprint:
    """Hash a JSON-compatible mapping using a canonical representation."""
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return ConfigurationFingerprint(value=digest)


def fingerprint_model(model: BaseModel) -> ConfigurationFingerprint:
    """Hash the JSON representation of a Pydantic model."""
    return fingerprint_payload(model.model_dump(mode="json"))
