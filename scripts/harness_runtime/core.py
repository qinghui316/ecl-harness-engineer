"""Shared errors, identifiers, paths, atomic I/O, process execution, and fingerprints."""

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

SCHEMA_VERSION = "1.0"

MANIFEST_SCHEMA_VERSION = "2.0"

EVOLUTION_THRESHOLD = 5

TEXT_SUFFIXES = {".md", ".json", ".txt", ".tsv", ".tpl", ".py", ".ps1", ".sh", ".mjs"}

REQUIRED_CHANGE_FILES = {
    "summary.md", "spec.md", "plan.md", "tasks.md", "reviews/review.md",
}

_UNSET = object()

_CONTENT_GUARD_LOCAL = threading.local()

TERMINAL_CHANGE_STATUSES = {"completed", "blocked", "abandoned"}

ID_MAX_LENGTH = 96

MANAGED_ROUTE_BEGIN = "<!-- ECL-HARNESS:BEGIN -->"

MANAGED_ROUTE_END = "<!-- ECL-HARNESS:END -->"

MANAGED_CONNECTOR_MARKER = "ECL-HARNESS-CONNECTOR"

MAX_ROUTE_BYTES = 512 * 1024

class HarnessError(RuntimeError):
    pass

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def normalize_path(path: Path) -> str:
    value = str(path.resolve())
    return os.path.normcase(value).replace("\\", "/")

def normalize_lexical_path(path: Path) -> str:
    value = os.path.abspath(path)
    return os.path.normcase(value).replace("\\", "/")

def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"

def canonical_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError(f"{label} must be a non-empty identifier.")
    raw = value.strip()
    if any(character in raw for character in ("/", "\\", "\0")) or raw in {".", ".."}:
        raise HarnessError(f"{label} must not contain path separators or traversal segments: {value!r}")
    if not re.search(r"[A-Za-z0-9]", raw):
        raise HarnessError(f"{label} must contain at least one letter or digit: {value!r}")
    canonical = slugify(raw)
    if len(canonical) > ID_MAX_LENGTH:
        raise HarnessError(f"{label} exceeds {ID_MAX_LENGTH} canonical characters.")
    return canonical

def stable_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]

def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise HarnessError(f"Command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result

def git(project_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", "-C", str(project_root), *args], check=check)

def git_value(project_root: Path, *args: str) -> str | None:
    result = git(project_root, *args, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None

def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2))

def atomic_create_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise HarnessError(f"Record already exists: {path.name}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except Exception:
        if path.exists():
            path.unlink()
        raise

def atomic_append_tsv(path: Path, values: list[str]) -> None:
    line = "\t".join(value.replace("\t", " ").replace("\n", " ") for value in values)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    atomic_write_text(path, existing.rstrip("\n") + "\n" + line)

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise HarnessError(f"Invalid JSON in {path}: {exc}") from exc

def render(value: str, replacements: dict[str, str]) -> str:
    for key, replacement in replacements.items():
        value = value.replace("{{" + key + "}}", replacement)
    return value

def is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    return bool(is_junction and is_junction(path))

def reject_linked_ancestors(base: Path, target: Path, label: str) -> None:
    base_lexical = Path(os.path.abspath(base))
    target_lexical = Path(os.path.abspath(target))
    try:
        relative = target_lexical.relative_to(base_lexical)
    except ValueError as exc:
        raise HarnessError(f"{label} escapes its project root: {target_lexical}") from exc
    current = base_lexical
    if is_link_like(current):
        raise HarnessError(f"{label} has a linked project root: {current}")
    for part in relative.parts:
        current = current / part
        if (current.exists() or current.is_symlink()) and is_link_like(current):
            raise HarnessError(f"{label} must not traverse a link or junction: {current}")

def reject_tree_links(root: Path, label: str) -> None:
    if is_link_like(root):
        raise HarnessError(f"{label} must be a physical directory, not a link: {root}")
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                if is_link_like(path):
                    raise HarnessError(f"{label} must not contain links: {path}")
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)

def file_fingerprint(paths: Iterable[Path], root: Path | None = None) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        identity = path.relative_to(root).as_posix() if root and is_within(path, root) else str(path)
        digest.update(identity.encode("utf-8"))
        try:
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(64 * 1024), b""):
                    digest.update(block)
        except OSError:
            digest.update(b"missing")
    return digest.hexdigest()

def safe_relative(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError(f"{label} must be a non-empty project-relative path.")
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if (
        "\0" in normalized
        or re.match(r"^[A-Za-z]:", normalized)
        or normalized.startswith("//")
        or path.is_absolute()
        or ".." in path.parts
        or not path.parts
    ):
        raise HarnessError(f"{label} must be a project-relative path: {value}")
    return path.as_posix()
