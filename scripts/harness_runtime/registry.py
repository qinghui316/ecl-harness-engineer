"""Bound Registry record access and Lane identity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import HarnessError, canonical_id, read_json, stable_hash

def registry_root(skill_root: Path) -> Path:
    return skill_root / "state" / "registry"

def records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    result = []
    for item in sorted(path.glob("*.json")):
        value = read_json(item)
        if isinstance(value, dict):
            result.append(value)
    return result

def bound_records(path: Path, id_field: str, label: str) -> list[dict[str, Any]]:
    result = []
    if not path.exists():
        return result
    for item in sorted(path.glob("*.json")):
        expected = canonical_id(item.stem, f"{label} filename")
        if expected != item.stem:
            raise HarnessError(f"Non-canonical {label} record filename: {item.name}")
        value = read_json(item)
        if not isinstance(value, dict) or value.get(id_field) != expected:
            raise HarnessError(f"{label} record id does not match its filename: {item.name}")
        result.append(value)
    return result

def lane_id(context: dict[str, Any]) -> str:
    if context.get("mode") == "single_lane":
        return "lane-single"
    branch = context.get("branch")
    if not branch:
        raise HarnessError("Structured Change work requires a named Git branch; detached HEAD has no stable Lane identity.")
    project_id = context.get("project_id")
    if not project_id:
        raise HarnessError("Project identity is required before resolving a Lane.")
    return f"lane-{stable_hash(f'{project_id}:{branch}', 10)}"
