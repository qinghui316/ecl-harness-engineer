"""Bound Registry record access and Lane identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .core import HarnessError, canonical_id, normalize_path, read_json, stable_hash

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
    return f"lane-{stable_hash(normalize_path(context['project_root']), 10)}"
