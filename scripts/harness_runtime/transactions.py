"""Coordination Registry locks and crash-recoverable content transactions."""

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

from .core import HarnessError, SCHEMA_VERSION, _CONTENT_GUARD_LOCAL, atomic_write_bytes, atomic_write_json, canonical_id, git, git_value, is_link_like, is_within, normalize_path, read_json, reject_tree_links, remove_owned_tree, safe_relative, unlink_directory_link_node, utc_now
from .project import project_context, skill_root_for
from .registry import registry_root

CONTENT_TRANSACTION_PATHS = ("SKILL.md", "references", "scripts", "assets", "agents")
REPOSITORY_SIDECAR_NAMES = (".git", ".gitignore", ".gitattributes", ".github", "README.md")
FILE_SET_TRANSACTION_MODE = "file-set-v1"
COMMITTED_TRANSACTION_MARKER_SUFFIX = ".committed.json"
CONTENT_INDEX_PATHS = {
    "references/project_wiki/catalog.md",
    "references/project_wiki/.ecl-baselines.json",
}
FILE_SET_ACTIONS = {
    "create-file",
    "replace-file",
    "retire-file",
    "file-to-directory",
    "directory-to-file",
    "create-directory",
    "remove-directory",
}


def git_repository_findings(skill_root: Path) -> list[dict[str, Any]]:
    metadata = skill_root / ".git"
    if not path_present(metadata):
        return []
    if is_link_like(metadata):
        return [{"type": "linked_skill_git_metadata", "path": str(metadata)}]
    findings: list[dict[str, Any]] = []
    top_level = git_value(skill_root, "rev-parse", "--show-toplevel")
    if not top_level:
        return [{"type": "invalid_skill_git_repository", "path": str(metadata)}]
    if normalize_path(Path(top_level)) != normalize_path(skill_root):
        findings.append({
            "type": "wrong_skill_git_top_level",
            "expected": str(skill_root),
            "actual": top_level,
        })
    unmerged = git(skill_root, "ls-files", "-u", check=False)
    if unmerged.returncode != 0:
        findings.append({"type": "unreadable_skill_git_index"})
    elif unmerged.stdout.strip():
        findings.append({"type": "unmerged_skill_git_index"})
    git_dir_value = git_value(skill_root, "rev-parse", "--git-dir")
    if not git_dir_value:
        findings.append({"type": "unresolvable_skill_git_dir"})
        return findings
    git_dir = Path(git_dir_value)
    if not git_dir.is_absolute():
        git_dir = (skill_root / git_dir).resolve()
    operation_paths = {
        "index.lock": "skill_git_index_locked",
        "MERGE_HEAD": "skill_git_merge_in_progress",
        "CHERRY_PICK_HEAD": "skill_git_cherry_pick_in_progress",
        "REVERT_HEAD": "skill_git_revert_in_progress",
        "rebase-apply": "skill_git_rebase_in_progress",
        "rebase-merge": "skill_git_rebase_in_progress",
    }
    for relative, finding_type in operation_paths.items():
        if (git_dir / relative).exists():
            findings.append({"type": finding_type, "path": str(git_dir / relative)})
    return findings


def repository_sidecars(skill_root: Path) -> list[str]:
    result = [name for name in REPOSITORY_SIDECAR_NAMES if path_present(skill_root / name)]
    for path in sorted(skill_root.glob("LICENSE*"), key=lambda item: item.name.lower()):
        if path.name not in result:
            result.append(path.name)
    for relative in result:
        path = skill_root / relative
        if is_link_like(path):
            raise HarnessError(f"Project Skill repository sidecar must not be a link: {path}")
    return result

def writer_lock_path(skill_root: Path) -> Path:
    return registry_root(skill_root) / "locks" / "shared-writer"

def acquire_writer(skill_root: Path, kind: str, owner_id: str) -> Path:
    lock = writer_lock_path(skill_root)
    try:
        lock.mkdir()
    except FileExistsError as exc:
        current = read_json(lock / "owner.json", {})
        if current.get("kind") == kind and current.get("owner_id") == owner_id:
            return lock
        raise HarnessError(
            f"Shared project Harness writer is already owned by {current.get('kind', 'unknown')}:"
            f"{current.get('owner_id', 'unknown')}."
        ) from exc
    atomic_write_json(
        lock / "owner.json",
        {"kind": kind, "owner_id": owner_id, "claimed_at": utc_now()},
    )
    return lock

def release_writer(skill_root: Path, kind: str, owner_id: str) -> None:
    lock = writer_lock_path(skill_root)
    current = read_json(lock / "owner.json", {})
    if not lock.exists():
        return
    if current.get("kind") != kind or current.get("owner_id") != owner_id:
        raise HarnessError("Refusing to release a shared writer owned by another operation.")
    remove_owned_tree(lock, lock.parent, "Shared writer lock")

@contextmanager
def short_registry_lock(skill_root: Path, name: str, *, timeout_seconds: float = 10.0):
    lock = registry_root(skill_root) / "locks" / name
    lock.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                owner = read_json(lock / "owner.json", {})
                raise HarnessError(
                    f"Timed out waiting for Registry lock {name}; current owner is "
                    f"{owner.get('token', 'unknown')}."
                )
            time.sleep(0.025)
    try:
        atomic_write_json(lock / "owner.json", {"token": token, "claimed_at": utc_now()})
        yield
    finally:
        owner = read_json(lock / "owner.json", {})
        if owner.get("token") == token and lock.exists():
            remove_owned_tree(lock, lock.parent, "Registry lock")

def try_lock_file(handle: Any) -> bool:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False

def unlock_file(handle: Any) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

@contextmanager
def content_publication_guard(skill_root: Path, *, timeout_seconds: float = 30.0):
    key = normalize_path(skill_root)
    held = getattr(_CONTENT_GUARD_LOCAL, "held", set())
    if key in held:
        yield
        return
    lock_path = skill_root.parent / ".harness-operation-locks" / f"{skill_root.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    handle = None
    while handle is None:
        try:
            candidate = lock_path.open("a+b")
        except FileNotFoundError:
            if time.monotonic() >= deadline:
                raise HarnessError("Timed out waiting for the current project Harness update to finish.")
            time.sleep(0.025)
            continue
        if candidate.tell() == 0:
            candidate.write(b"0")
            candidate.flush()
        if try_lock_file(candidate):
            handle = candidate
            break
        candidate.close()
        if time.monotonic() >= deadline:
            raise HarnessError("Timed out waiting for the project Harness filesystem operation lock.")
        time.sleep(0.025)
    held.add(key)
    _CONTENT_GUARD_LOCAL.held = held
    try:
        yield
    finally:
        held.remove(key)
        unlock_file(handle)
        handle.close()

def guard_project_skill(function: Any) -> Any:
    def guarded(args: argparse.Namespace) -> dict[str, Any]:
        context = project_context(Path(args.project_root))
        try:
            root = skill_root_for(context, args)
        except HarnessError:
            return function(args)
        if not (root / "state" / "manifest.json").exists() and not content_transaction_store(root).exists():
            return function(args)
        with content_publication_guard(root):
            if function.__name__ != "project_doctor":
                recover_all_content_transactions(root)
            return function(args)

    guarded.__name__ = function.__name__
    guarded.__doc__ = function.__doc__
    return guarded

@contextmanager
def project_skill_read_guard(skill_root: Path):
    with content_publication_guard(skill_root):
        store = content_transaction_store(skill_root)
        if store.exists() and any(store.iterdir()):
            raise HarnessError(
                "Project Harness has an incomplete content transaction; run project doctor and an "
                "explicit mutating recovery command before read-only inspection."
            )
        yield

def guard_project_skill_read_only(function: Any) -> Any:
    def guarded(args: argparse.Namespace) -> dict[str, Any]:
        context = project_context(Path(args.project_root))
        try:
            root = skill_root_for(context, args)
        except HarnessError:
            return function(args)
        with project_skill_read_guard(root):
            return function(args)

    guarded.__name__ = function.__name__
    guarded.__doc__ = function.__doc__
    return guarded

def path_present(path: Path) -> bool:
    return path.exists() or is_link_like(path)

def transaction_move(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)

def transaction_journal(transaction_root: Path, value: dict[str, Any]) -> None:
    durable_atomic_write_json(transaction_root / "journal.json", value)

def durable_atomic_write_json(path: Path, value: Any) -> None:
    content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    durable_atomic_write_bytes(path, content)

def durable_atomic_write_bytes(path: Path, content: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temp_name, mode)
        replace_with_retry(Path(temp_name), path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

def replace_with_retry(source: Path, target: Path) -> None:
    deadline = time.monotonic() + 2.0
    delay = 0.025
    while True:
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32} or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)

def unlink_with_retry(path: Path) -> None:
    deadline = time.monotonic() + 2.0
    delay = 0.025
    while True:
        try:
            path.unlink()
            return
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32} or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)

def rmdir_with_retry(path: Path) -> None:
    deadline = time.monotonic() + 2.0
    delay = 0.025
    while True:
        try:
            path.rmdir()
            return
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32} or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)

def remove_transaction_path(path: Path) -> None:
    if not path_present(path):
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif is_link_like(path):
        unlink_directory_link_node(path)
    else:
        remove_owned_tree(path, path.parent, "Content transaction path")

def copy_transaction_path(source: Path, target: Path) -> None:
    if is_link_like(source):
        raise HarnessError(f"Content transaction source must not be a link: {source}")
    if source.is_dir():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

def content_transaction_store(skill_root: Path) -> Path:
    return skill_root.parent / f".{skill_root.name}.content-transactions"

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def ignored_content_file(relative: Path) -> bool:
    return "__pycache__" in relative.parts or relative.suffix == ".pyc"

def managed_relative(relative: str, label: str = "managed content path") -> str:
    normalized = safe_relative(relative, label)
    path = Path(normalized)
    if path.parts[0] not in CONTENT_TRANSACTION_PATHS:
        raise HarnessError(f"{label.title()} is outside managed content: {relative}")
    if path.parts[0] == "SKILL.md" and len(path.parts) != 1:
        raise HarnessError(f"{label.title()} is below the SKILL.md file: {relative}")
    return normalized

def content_inventory(root: Path, label: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    files: dict[str, dict[str, Any]] = {}
    directories: dict[str, dict[str, Any]] = {}
    identities: dict[str, str] = {}

    def add_identity(relative: str) -> None:
        key = os.path.normcase(relative)
        previous = identities.get(key)
        if previous is not None and previous != relative:
            raise HarnessError(f"{label} contains colliding paths: {previous} and {relative}")
        identities[key] = relative

    for owner in CONTENT_TRANSACTION_PATHS:
        owner_path = root / owner
        if not path_present(owner_path):
            continue
        if is_link_like(owner_path):
            raise HarnessError(f"{label} must not contain links: {owner_path}")
        if owner_path.is_file():
            if owner != "SKILL.md":
                raise HarnessError(f"{label} managed directory is a file: {owner_path}")
            add_identity(owner)
            files[owner] = {
                "kind": "file",
                "sha256": file_sha256(owner_path),
                "mode": owner_path.stat().st_mode & 0o777,
                "ignored": False,
            }
            continue
        if not owner_path.is_dir() or owner == "SKILL.md":
            raise HarnessError(f"{label} has an invalid managed content node: {owner_path}")
        pending = [owner_path]
        while pending:
            directory = pending.pop()
            relative_directory = directory.relative_to(root).as_posix()
            add_identity(relative_directory)
            directories[relative_directory] = {
                "kind": "directory",
                "mode": directory.stat().st_mode & 0o777,
            }
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    relative = path.relative_to(root).as_posix()
                    if is_link_like(path):
                        raise HarnessError(f"{label} must not contain links: {path}")
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(path)
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        raise HarnessError(f"{label} contains a non-file node: {path}")
                    add_identity(relative)
                    relative_path = Path(relative)
                    files[relative] = {
                        "kind": "file",
                        "sha256": file_sha256(path),
                        "mode": path.stat().st_mode & 0o777,
                        "ignored": ignored_content_file(relative_path),
                    }
    return files, directories

def managed_content_digest(skill_root: Path) -> str:
    files, _ = content_inventory(skill_root, "Project Harness content")
    digest = hashlib.sha256()
    # Preserve the historical Evolution digest order so already reviewed
    # candidates remain valid after the transaction implementation changes.
    for owner in CONTENT_TRANSACTION_PATHS:
        for relative in sorted(
            path for path in files if Path(path).parts[0] == owner
        ):
            if files[relative].get("ignored"):
                continue
            digest.update(relative.encode("utf-8"))
            with (skill_root / relative).open("rb") as handle:
                for block in iter(lambda: handle.read(64 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def operation_priority(operation: dict[str, Any]) -> tuple[int, int, str]:
    action = operation["action"]
    relative = operation["path"]
    depth = len(Path(relative).parts)
    if operation.get("topology"):
        if action == "retire-file":
            return (0, -depth, relative)
        if action == "remove-directory":
            return (1, -depth, relative)
        if action in {"file-to-directory", "create-directory"}:
            return (2, depth, relative)
        return (3, depth, relative)
    if action == "create-directory":
        return (4, depth, relative)
    if action in {"create-file", "replace-file"}:
        if relative in CONTENT_INDEX_PATHS:
            return (6, depth, relative)
        if relative == "SKILL.md":
            return (7, depth, relative)
        return (5, depth, relative)
    return (8, -depth, relative)

def build_file_set_operations(
    current_files: dict[str, dict[str, Any]],
    current_directories: dict[str, dict[str, Any]],
    candidate_files: dict[str, dict[str, Any]],
    candidate_directories: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    directory_to_file = {path for path in candidate_files if path in current_directories}
    file_to_directory = {path for path in candidate_directories if path in current_files}

    def below_any(relative: str, parents: set[str]) -> bool:
        path = Path(relative)
        return any(parent != relative and Path(parent) in path.parents for parent in parents)

    for relative, current in current_files.items():
        if current.get("ignored") and not below_any(relative, directory_to_file):
            continue
        candidate = candidate_files.get(relative)
        if candidate is not None:
            if current["sha256"] != candidate["sha256"] or current["mode"] != candidate["mode"]:
                operations.append({"path": relative, "action": "replace-file", "before": current, "after": candidate})
            continue
        if relative in file_to_directory:
            operations.append({
                "path": relative,
                "action": "file-to-directory",
                "before": current,
                "after": candidate_directories[relative],
                "topology": True,
            })
        else:
            operations.append({
                "path": relative,
                "action": "retire-file",
                "before": current,
                "after": None,
                "topology": below_any(relative, directory_to_file),
            })

    for relative, candidate in candidate_files.items():
        if candidate.get("ignored") or relative in current_files:
            continue
        if relative in directory_to_file:
            operations.append({
                "path": relative,
                "action": "directory-to-file",
                "before": current_directories[relative],
                "after": candidate,
                "topology": True,
            })
        else:
            operations.append({"path": relative, "action": "create-file", "before": None, "after": candidate})

    for relative, candidate in candidate_directories.items():
        if relative in current_directories or relative in file_to_directory:
            continue
        operations.append({
            "path": relative,
            "action": "create-directory",
            "before": None,
            "after": candidate,
            "topology": below_any(relative, file_to_directory),
        })

    for relative, current in current_directories.items():
        if relative in candidate_directories or relative in directory_to_file:
            continue
        if below_any(relative, directory_to_file):
            operations.append({
                "path": relative,
                "action": "remove-directory",
                "before": current,
                "after": None,
                "topology": True,
            })

    operations.sort(key=operation_priority)
    for index, operation in enumerate(operations):
        operation["index"] = index
    return operations

def validate_state_snapshots(
    transaction: dict[str, Any],
    transaction_root: Path,
) -> None:
    snapshots = transaction.get("state_snapshots", {})
    if not isinstance(snapshots, dict):
        raise HarnessError("Content transaction state snapshots must be an object.")
    for relative, snapshot in snapshots.items():
        normalized = safe_relative(relative, "transaction state snapshot")
        if not normalized.startswith("state/") or not isinstance(snapshot, dict):
            raise HarnessError("Content transaction snapshot target must stay below state/.")
        snapshot_path = Path(str(snapshot.get("path", ""))).resolve()
        if not is_within(snapshot_path, transaction_root):
            raise HarnessError("Content transaction snapshot backup points outside its journal directory.")

def validate_legacy_content_transaction_record(
    transaction: dict[str, Any],
    expected_skill_root: Path | None = None,
) -> None:
    required = (
        "skill_root", "candidate", "transaction_root", "replacement", "backup",
        "original_analysis", "operation", "transaction_id", "phase",
    )
    if not isinstance(transaction, dict) or any(not isinstance(transaction.get(key), str) for key in required):
        raise HarnessError("Content transaction recovery journal is incomplete.")
    skill_root = Path(transaction["skill_root"]).resolve()
    if expected_skill_root and normalize_path(skill_root) != normalize_path(expected_skill_root):
        raise HarnessError("Content transaction belongs to another project Harness.")
    store = content_transaction_store(skill_root).resolve()
    transaction_root = Path(transaction["transaction_root"]).resolve()
    if transaction_root == store or not is_within(transaction_root, store):
        raise HarnessError("Content transaction journal points outside its transaction store.")
    for field in ("replacement", "backup", "original_analysis"):
        value = Path(transaction[field]).resolve()
        if value == transaction_root or not is_within(value, transaction_root):
            raise HarnessError(f"Content transaction {field} points outside its journal directory.")
    candidate = Path(transaction["candidate"]).resolve()
    if not is_within(candidate, skill_root / "state"):
        raise HarnessError("Content transaction candidate points outside project Harness state.")
    validate_state_snapshots(transaction, transaction_root)
    sidecars = transaction.get("repository_sidecars", [])
    if not isinstance(sidecars, list):
        raise HarnessError("Content transaction repository sidecars must be an array.")
    allowed = set(REPOSITORY_SIDECAR_NAMES)
    for relative in sidecars:
        if (
            not isinstance(relative, str)
            or safe_relative(relative, "repository sidecar") != relative
            or len(Path(relative).parts) != 1
            or (relative not in allowed and not relative.startswith("LICENSE"))
        ):
            raise HarnessError(f"Content transaction has an invalid repository sidecar: {relative!r}")

def load_file_set_operations(transaction: dict[str, Any]) -> list[dict[str, Any]]:
    operations_path = Path(transaction["operations_path"])
    if not operations_path.is_file():
        raise HarnessError("File-set transaction operation plan is missing.")
    operations = read_json(operations_path, None)
    if not isinstance(operations, list):
        raise HarnessError("File-set transaction operation plan must be an array.")
    seen: set[str] = set()
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("index") != index:
            raise HarnessError("File-set transaction operation indexes are invalid.")
        action = operation.get("action")
        relative = managed_relative(operation.get("path"), "transaction operation path")
        identity = os.path.normcase(relative)
        if identity in seen:
            raise HarnessError(f"File-set transaction repeats a managed path: {relative}")
        seen.add(identity)
        if action not in FILE_SET_ACTIONS:
            raise HarnessError(f"File-set transaction has an unsupported action: {action}")
        for state_name in ("before", "after"):
            state = operation.get(state_name)
            if state is None:
                continue
            if not isinstance(state, dict) or state.get("kind") not in {"file", "directory"}:
                raise HarnessError(f"File-set transaction {state_name} state is invalid: {relative}")
            if state.get("kind") == "file" and not isinstance(state.get("sha256"), str):
                raise HarnessError(f"File-set transaction file digest is missing: {relative}")
        backup = operation.get("backup")
        if backup is not None:
            backup_path = Path(str(backup)).resolve()
            transaction_root = Path(transaction["transaction_root"]).resolve()
            if not is_within(backup_path, transaction_root):
                raise HarnessError("File-set transaction backup points outside its journal directory.")
        temp_relative = operation.get("temp_path")
        if temp_relative is not None:
            normalized_temp = safe_relative(temp_relative, "transaction temporary file")
            temp_path = Path(transaction["skill_root"]) / normalized_temp
            if normalize_path(temp_path) == normalize_path(Path(transaction["skill_root"]) / relative):
                raise HarnessError("File-set transaction temporary file collides with its target.")
            if not is_within(temp_path, Path(transaction["skill_root"])):
                raise HarnessError("File-set transaction temporary file escapes the project Harness.")
    return operations

def validate_file_set_content_transaction_record(
    transaction: dict[str, Any],
    expected_skill_root: Path | None = None,
) -> None:
    required = (
        "skill_root", "candidate", "transaction_root", "operations_path",
        "operation", "transaction_id", "phase", "base_content_digest", "candidate_content_digest",
    )
    if not isinstance(transaction, dict) or any(not isinstance(transaction.get(key), str) for key in required):
        raise HarnessError("File-set transaction recovery journal is incomplete.")
    if transaction.get("transaction_mode") != FILE_SET_TRANSACTION_MODE:
        raise HarnessError(f"Unsupported content transaction mode: {transaction.get('transaction_mode')!r}")
    skill_root = Path(transaction["skill_root"]).resolve()
    if expected_skill_root and normalize_path(skill_root) != normalize_path(expected_skill_root):
        raise HarnessError("Content transaction belongs to another project Harness.")
    store = content_transaction_store(skill_root).resolve()
    transaction_root = Path(transaction["transaction_root"]).resolve()
    if transaction_root == store or not is_within(transaction_root, store):
        raise HarnessError("Content transaction journal points outside its transaction store.")
    candidate = Path(transaction["candidate"]).resolve()
    if not is_within(candidate, skill_root / "state"):
        raise HarnessError("Content transaction candidate points outside project Harness state.")
    operations_path = Path(transaction["operations_path"]).resolve()
    if not is_within(operations_path, transaction_root):
        raise HarnessError("File-set transaction operation plan points outside its journal directory.")
    validate_state_snapshots(transaction, transaction_root)
    progress = transaction.get("progress", {})
    if not isinstance(progress, dict):
        raise HarnessError("File-set transaction progress must be an object.")
    phase = transaction.get("phase")
    if phase not in {"preparing", "prepared", "applying_content", "content_applied", "committing", "committed"}:
        raise HarnessError(f"File-set transaction has an invalid phase: {phase}")
    if phase not in {"preparing", "committing", "committed"}:
        load_file_set_operations(transaction)

def validate_content_transaction_record(
    transaction: dict[str, Any],
    expected_skill_root: Path | None = None,
) -> None:
    mode = transaction.get("transaction_mode") if isinstance(transaction, dict) else None
    if mode is None:
        validate_legacy_content_transaction_record(transaction, expected_skill_root)
    elif mode == FILE_SET_TRANSACTION_MODE:
        validate_file_set_content_transaction_record(transaction, expected_skill_root)
    else:
        raise HarnessError(f"Unsupported content transaction mode: {mode!r}")

def rollback_legacy_content_transaction(transaction: dict[str, Any]) -> None:
    validate_legacy_content_transaction_record(transaction)
    skill_root = Path(transaction["skill_root"])
    transaction_root = Path(transaction["transaction_root"])
    replacement = Path(transaction["replacement"])
    backup = Path(transaction["backup"])
    original_analysis = Path(transaction["original_analysis"])
    state_holder: Path | None = None
    if path_present(backup):
        if path_present(skill_root):
            remove_transaction_path(replacement)
            transaction_move(skill_root, replacement)
            state_holder = replacement
        elif path_present(replacement):
            state_holder = replacement
        preserved = ["state", *transaction.get("repository_sidecars", [])]
        for relative in preserved:
            source = state_holder / relative if state_holder else None
            if path_present(backup / relative) or source is None or not path_present(source):
                continue
            if relative == "state" and path_present(original_analysis):
                remove_transaction_path(source / "analysis")
                transaction_move(original_analysis, source / "analysis")
            transaction_move(source, backup / relative)
        if not path_present(skill_root):
            transaction_move(backup, skill_root)
    remove_transaction_path(replacement)
    for relative, snapshot in transaction.get("state_snapshots", {}).items():
        target = skill_root / relative
        snapshot_path = Path(snapshot["path"])
        if snapshot.get("present"):
            if not snapshot_path.is_file():
                raise HarnessError(f"Transaction state snapshot is missing: {relative}")
            atomic_write_bytes(target, snapshot_path.read_bytes())
        elif path_present(target):
            remove_transaction_path(target)
    if transaction_root.exists():
        remove_owned_tree(transaction_root, transaction_root.parent, "Content transaction journal")
    store = content_transaction_store(skill_root)
    if store.exists() and not any(store.iterdir()):
        store.rmdir()

def restore_state_snapshots(transaction: dict[str, Any]) -> None:
    skill_root = Path(transaction["skill_root"])
    for relative, snapshot in transaction.get("state_snapshots", {}).items():
        target = skill_root / relative
        snapshot_path = Path(snapshot["path"])
        if snapshot.get("present"):
            if not snapshot_path.is_file():
                raise HarnessError(f"Transaction state snapshot is missing: {relative}")
            durable_atomic_write_bytes(target, snapshot_path.read_bytes())
        elif path_present(target):
            remove_transaction_path(target)

def backup_for_operation(transaction_root: Path, operation: dict[str, Any], skill_root: Path) -> None:
    before = operation.get("before")
    if not before or before.get("kind") != "file":
        return
    relative = operation["path"]
    source = skill_root / relative
    if not source.is_file() or file_sha256(source) != before["sha256"]:
        raise HarnessError(f"Managed content changed while preparing the transaction: {relative}")
    backup = transaction_root / "backups" / relative
    durable_atomic_write_bytes(backup, source.read_bytes(), before.get("mode"))
    if file_sha256(backup) != before["sha256"]:
        raise HarnessError(f"Content transaction backup verification failed: {relative}")
    operation["backup"] = str(backup)

def verify_candidate_operation(candidate: Path, operation: dict[str, Any]) -> bytes:
    relative = operation["path"]
    expected = operation.get("after")
    source = candidate / relative
    if not expected or expected.get("kind") != "file" or not source.is_file():
        raise HarnessError(f"Content candidate file is missing: {relative}")
    content = source.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected["sha256"]:
        raise HarnessError(f"Content candidate was modified during publication: {relative}")
    return content

def write_operation_file(
    skill_root: Path,
    target: Path,
    content: bytes,
    mode: int | None,
    operation: dict[str, Any],
) -> None:
    temp_relative = operation.get("temp_path")
    if not isinstance(temp_relative, str):
        raise HarnessError(f"File-set transaction temporary path is missing: {operation['path']}")
    temp = skill_root / safe_relative(temp_relative, "transaction temporary file")
    if not is_within(temp, skill_root) or temp.parent != target.parent:
        raise HarnessError(f"File-set transaction temporary path is unsafe: {operation['path']}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if path_present(temp):
        if not temp.is_file() or is_link_like(temp):
            raise HarnessError(f"File-set transaction temporary path is unsafe: {temp}")
        unlink_with_retry(temp)
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temp, mode)
        replace_with_retry(temp, target)
    finally:
        if path_present(temp):
            unlink_with_retry(temp)

def current_file_digest(path: Path) -> str | None:
    return file_sha256(path) if path.is_file() else None

def assert_current_before(path: Path, operation: dict[str, Any]) -> None:
    before = operation.get("before")
    if before is None:
        if path_present(path):
            raise HarnessError(f"Managed content appeared during publication: {operation['path']}")
        return
    if before["kind"] == "file":
        if current_file_digest(path) != before["sha256"]:
            raise HarnessError(f"Managed content changed during publication: {operation['path']}")
    elif not path.is_dir() or is_link_like(path):
        raise HarnessError(f"Managed directory changed during publication: {operation['path']}")

def apply_file_set_operation(
    skill_root: Path,
    candidate: Path,
    operation: dict[str, Any],
    transaction_id: str,
) -> None:
    relative = operation["path"]
    target = skill_root / relative
    action = operation["action"]
    assert_current_before(target, operation)
    if action == "create-directory":
        target.mkdir()
        os.chmod(target, operation["after"].get("mode", 0o755))
    elif action == "remove-directory":
        rmdir_with_retry(target)
    elif action == "file-to-directory":
        unlink_with_retry(target)
        target.mkdir()
        os.chmod(target, operation["after"].get("mode", 0o755))
    elif action == "directory-to-file":
        rmdir_with_retry(target)
        content = verify_candidate_operation(candidate, operation)
        write_operation_file(skill_root, target, content, operation["after"].get("mode"), operation)
    elif action in {"create-file", "replace-file"}:
        content = verify_candidate_operation(candidate, operation)
        write_operation_file(skill_root, target, content, operation["after"].get("mode"), operation)
    elif action == "retire-file":
        unlink_with_retry(target)
    else:
        raise HarnessError(f"Unsupported file-set operation: {action}")
    verify_file_set_operation_after(skill_root, operation)

def verify_file_set_operation_after(skill_root: Path, operation: dict[str, Any]) -> None:
    target = skill_root / operation["path"]
    after = operation.get("after")
    if after is None:
        if path_present(target):
            raise HarnessError(f"Managed content retirement did not complete: {operation['path']}")
    elif after["kind"] == "file":
        if current_file_digest(target) != after["sha256"]:
            raise HarnessError(f"Managed content write verification failed: {operation['path']}")
    elif not target.is_dir() or is_link_like(target):
        raise HarnessError(f"Managed directory update verification failed: {operation['path']}")

def restore_operation_backup(skill_root: Path, target: Path, operation: dict[str, Any]) -> None:
    before = operation.get("before")
    backup = operation.get("backup")
    if not before or before.get("kind") != "file" or not backup:
        raise HarnessError(f"Content transaction backup is missing: {operation['path']}")
    backup_path = Path(backup)
    if not backup_path.is_file() or file_sha256(backup_path) != before["sha256"]:
        raise HarnessError(f"Content transaction backup is invalid: {operation['path']}")
    write_operation_file(skill_root, target, backup_path.read_bytes(), before.get("mode"), operation)

def rollback_file_set_operation(skill_root: Path, operation: dict[str, Any]) -> None:
    target = skill_root / operation["path"]
    action = operation["action"]
    before = operation.get("before")
    after = operation.get("after")
    temp_relative = operation.get("temp_path")
    if isinstance(temp_relative, str):
        temp = skill_root / safe_relative(temp_relative, "transaction temporary file")
        if path_present(temp):
            if not temp.is_file() or is_link_like(temp):
                raise HarnessError(f"External edit conflicts with transaction recovery: {temp_relative}")
            unlink_with_retry(temp)
    current_digest = current_file_digest(target)
    if action == "create-file":
        if not path_present(target):
            return
        if current_digest != after["sha256"]:
            raise HarnessError(f"External edit conflicts with transaction recovery: {operation['path']}")
        unlink_with_retry(target)
    elif action == "replace-file":
        if current_digest == before["sha256"]:
            return
        if current_digest != after["sha256"]:
            raise HarnessError(f"External edit conflicts with transaction recovery: {operation['path']}")
        restore_operation_backup(skill_root, target, operation)
    elif action == "retire-file":
        if current_digest == before["sha256"]:
            return
        if path_present(target):
            raise HarnessError(f"External edit conflicts with transaction recovery: {operation['path']}")
        restore_operation_backup(skill_root, target, operation)
    elif action == "create-directory":
        if not path_present(target):
            return
        if not target.is_dir() or any(target.iterdir()):
            raise HarnessError(f"External edit conflicts with directory recovery: {operation['path']}")
        rmdir_with_retry(target)
    elif action == "remove-directory":
        if target.is_dir() and not is_link_like(target):
            return
        if path_present(target):
            raise HarnessError(f"External edit conflicts with directory recovery: {operation['path']}")
        target.mkdir()
        os.chmod(target, before.get("mode", 0o755))
    elif action == "file-to-directory":
        if current_digest == before["sha256"]:
            return
        if not path_present(target):
            restore_operation_backup(skill_root, target, operation)
            return
        if not target.is_dir() or any(target.iterdir()):
            raise HarnessError(f"External edit conflicts with directory recovery: {operation['path']}")
        rmdir_with_retry(target)
        restore_operation_backup(skill_root, target, operation)
    elif action == "directory-to-file":
        if target.is_dir() and not is_link_like(target):
            return
        if not path_present(target):
            target.mkdir()
            os.chmod(target, before.get("mode", 0o755))
            return
        if current_digest != after["sha256"]:
            raise HarnessError(f"External edit conflicts with directory recovery: {operation['path']}")
        unlink_with_retry(target)
        target.mkdir()
        os.chmod(target, before.get("mode", 0o755))

def applied_operation_indexes(transaction: dict[str, Any], count: int) -> list[int]:
    phase = transaction.get("phase")
    if phase == "content_applied":
        return list(range(count))
    if phase != "applying_content":
        return []
    progress = transaction.get("progress", {})
    if progress == {}:
        return []
    index = progress.get("operation_index")
    status = progress.get("status")
    if not isinstance(index, int) or index < 0 or index >= count or status not in {"applying", "applied"}:
        raise HarnessError("File-set transaction progress is invalid.")
    limit = index + 1
    return list(range(limit))

def rollback_file_set_content_transaction(transaction: dict[str, Any]) -> None:
    validate_file_set_content_transaction_record(transaction)
    skill_root = Path(transaction["skill_root"])
    transaction_root = Path(transaction["transaction_root"])
    operations = [] if transaction.get("phase") == "preparing" else load_file_set_operations(transaction)
    for index in reversed(applied_operation_indexes(transaction, len(operations))):
        rollback_file_set_operation(skill_root, operations[index])
    restore_state_snapshots(transaction)
    if transaction_root.exists():
        remove_owned_tree(transaction_root, transaction_root.parent, "Content transaction journal")
    store = content_transaction_store(skill_root)
    if store.exists() and not any(store.iterdir()):
        store.rmdir()

def rollback_content_transaction(transaction: dict[str, Any]) -> None:
    if transaction.get("phase") in {"committing", "committed"}:
        raise HarnessError(
            "A content transaction in the commit phase cannot be rolled back; complete recovery instead."
        )
    if transaction.get("transaction_mode") is None:
        rollback_legacy_content_transaction(transaction)
    elif transaction.get("transaction_mode") == FILE_SET_TRANSACTION_MODE:
        rollback_file_set_content_transaction(transaction)
    else:
        raise HarnessError(f"Unsupported content transaction mode: {transaction.get('transaction_mode')!r}")

def apply_content_transaction(
    skill_root: Path,
    candidate: Path,
    operation: str,
    transaction_id: str,
    *,
    state_snapshot_paths: Iterable[Path] = (),
    expected_content_digest: str | None = None,
) -> dict[str, Any]:
    if operation not in {"evolution", "migration"}:
        raise HarnessError(f"Unsupported content transaction operation: {operation}")
    identifier = canonical_id(transaction_id, f"{operation.title()} transaction id")
    state_root = (skill_root / "state").resolve()
    if not is_within(candidate, state_root):
        raise HarnessError("Content candidate must live under project Harness state.")
    if not (candidate / "SKILL.md").is_file() or not (candidate / "references").is_dir():
        raise HarnessError("Content candidate is not a complete project Harness.")
    reject_tree_links(candidate, "Content candidate")
    repository_findings = git_repository_findings(skill_root)
    if repository_findings:
        raise HarnessError(
            "Project Skill Git repository is not safe for a stable content update: "
            + json.dumps(repository_findings, ensure_ascii=False)
        )
    current_files, current_directories = content_inventory(skill_root, "Current project Harness content")
    candidate_files, candidate_directories = content_inventory(candidate, "Content candidate")
    base_content_digest = managed_content_digest(skill_root)
    candidate_content_digest = managed_content_digest(candidate)
    if expected_content_digest is not None and candidate_content_digest != expected_content_digest:
        raise HarnessError("Content candidate digest does not match the independently reviewed candidate.")
    operations = build_file_set_operations(
        current_files,
        current_directories,
        candidate_files,
        candidate_directories,
    )
    transaction_root = content_transaction_store(skill_root) / f"{operation}-{identifier}-{secrets.token_hex(8)}"
    transaction_root.mkdir(parents=True, exist_ok=False)
    for item in operations:
        if (
            item["action"] in {"create-file", "replace-file", "directory-to-file"}
            or (item.get("before") or {}).get("kind") == "file"
        ):
            target = Path(item["path"])
            temp_name = f".{target.name}.{transaction_root.name}.{item['index']}.tmp"
            item["temp_path"] = (target.parent / temp_name).as_posix()
    state_snapshots: dict[str, dict[str, Any]] = {}
    operations_path = transaction_root / "operations.json"
    transaction = {
        "schema_version": SCHEMA_VERSION,
        "transaction_mode": FILE_SET_TRANSACTION_MODE,
        "operation": operation,
        "transaction_id": identifier,
        "skill_root": str(skill_root),
        "candidate": str(candidate),
        "transaction_root": str(transaction_root),
        "operations_path": str(operations_path),
        "base_content_digest": base_content_digest,
        "candidate_content_digest": candidate_content_digest,
        "state_snapshots": state_snapshots,
        "progress": {},
        "phase": "preparing",
        "created_at": utc_now(),
    }
    transaction_journal(transaction_root, transaction)
    try:
        for snapshot_path in state_snapshot_paths:
            resolved = snapshot_path.resolve()
            if not is_within(resolved, skill_root):
                raise HarnessError(f"Transaction state snapshot is outside the project Harness: {snapshot_path}")
            relative = resolved.relative_to(skill_root.resolve()).as_posix()
            backup_path = transaction_root / "state-snapshots" / relative
            present = snapshot_path.is_file()
            if present:
                durable_atomic_write_bytes(
                    backup_path,
                    snapshot_path.read_bytes(),
                    snapshot_path.stat().st_mode & 0o777,
                )
            state_snapshots[relative] = {"present": present, "path": str(backup_path)}
        for item in operations:
            backup_for_operation(transaction_root, item, skill_root)
        durable_atomic_write_json(operations_path, operations)
        transaction["phase"] = "prepared"
        transaction_journal(transaction_root, transaction)
        transaction["phase"] = "applying_content"
        transaction_journal(transaction_root, transaction)
        for item in operations:
            transaction["progress"] = {"operation_index": item["index"], "status": "applying"}
            transaction_journal(transaction_root, transaction)
            apply_file_set_operation(skill_root, candidate, item, identifier)
            transaction["progress"] = {"operation_index": item["index"], "status": "applied"}
            transaction_journal(transaction_root, transaction)
        transaction["phase"] = "content_applied"
        transaction["progress"] = {}
        transaction_journal(transaction_root, transaction)
        if managed_content_digest(candidate) != candidate_content_digest:
            raise HarnessError("Content candidate was modified during publication.")
        if managed_content_digest(skill_root) != candidate_content_digest:
            raise HarnessError("Applied project Harness content digest does not match the complete candidate.")
        return transaction
    except Exception as exc:
        rollback_content_transaction(transaction)
        if isinstance(exc, HarnessError):
            raise
        raise HarnessError(f"{operation.title()} content transaction failed: {exc}") from exc

def commit_legacy_content_transaction(transaction: dict[str, Any]) -> None:
    validate_legacy_content_transaction_record(transaction)
    transaction_root = Path(transaction["transaction_root"])
    candidate = Path(transaction["candidate"])
    transaction["phase"] = "committing"
    if transaction_root.exists():
        transaction_journal(transaction_root, transaction)
        remove_transaction_path(Path(transaction["backup"]))
        remove_transaction_path(Path(transaction["original_analysis"]))
        transaction["phase"] = "committed"
        transaction_journal(transaction_root, transaction)
    if candidate.exists():
        remove_owned_tree(candidate, candidate.parent, "Content transaction candidate")
    if transaction_root.exists():
        remove_owned_tree(transaction_root, transaction_root.parent, "Content transaction journal")
    store = content_transaction_store(Path(transaction["skill_root"]))
    if store.exists() and not any(store.iterdir()):
        store.rmdir()

def commit_file_set_content_transaction(transaction: dict[str, Any]) -> None:
    validate_file_set_content_transaction_record(transaction)
    transaction_root = Path(transaction["transaction_root"])
    candidate = Path(transaction["candidate"])
    if transaction.get("phase") not in {"committing", "committed"}:
        candidate_digest = transaction["candidate_content_digest"]
        if not candidate.is_dir() or managed_content_digest(candidate) != candidate_digest:
            rollback_file_set_content_transaction(transaction)
            raise HarnessError("Content candidate changed before transaction commit.")
        if managed_content_digest(Path(transaction["skill_root"])) != candidate_digest:
            rollback_file_set_content_transaction(transaction)
            raise HarnessError("Project Harness content changed before transaction commit.")
    if transaction_root.exists():
        committing = {**transaction, "phase": "committing"}
        transaction_journal(transaction_root, committing)
    transaction["phase"] = "committing"
    if candidate.exists():
        remove_owned_tree(candidate, candidate.parent, "Content transaction candidate")
    if transaction_root.exists():
        journal_path = transaction_root / "journal.json"
        for child in list(transaction_root.iterdir()):
            if child == journal_path:
                continue
            remove_transaction_path(child)
        committed = {**transaction, "phase": "committed"}
        transaction_journal(transaction_root, committed)
        transaction["phase"] = "committed"
        marker_path = committed_transaction_marker_path(transaction_root)
        if path_present(marker_path):
            raise HarnessError(f"Content transaction completion marker already exists: {marker_path}")
        replace_with_retry(journal_path, marker_path)
        rmdir_with_retry(transaction_root)
        unlink_with_retry(marker_path)
    store = content_transaction_store(Path(transaction["skill_root"]))
    if store.exists() and not any(store.iterdir()):
        store.rmdir()


def committed_transaction_marker_path(transaction_root: Path) -> Path:
    return transaction_root.parent / f".{transaction_root.name}{COMMITTED_TRANSACTION_MARKER_SUFFIX}"

def recover_committed_transaction_marker(
    skill_root: Path,
    marker_path: Path,
) -> None:
    transaction = read_json(marker_path, {})
    if not transaction:
        raise HarnessError(f"Content transaction completion marker is invalid: {marker_path}")
    validate_file_set_content_transaction_record(transaction, skill_root)
    if transaction.get("phase") != "committed":
        raise HarnessError(f"Content transaction completion marker is not committed: {marker_path}")
    transaction_root = Path(transaction["transaction_root"])
    if marker_path.resolve() != committed_transaction_marker_path(transaction_root).resolve():
        raise HarnessError(f"Content transaction completion marker identity is invalid: {marker_path}")
    if transaction_root.exists():
        if not transaction_root.is_dir() or is_link_like(transaction_root) or any(transaction_root.iterdir()):
            raise HarnessError(
                f"Committed content transaction directory is not empty: {transaction_root}"
            )
        rmdir_with_retry(transaction_root)
    unlink_with_retry(marker_path)


def recover_committed_transaction_markers(
    skill_root: Path,
    *,
    operation: str | None = None,
    transaction_id: str | None = None,
) -> None:
    root = content_transaction_store(skill_root)
    if not root.exists():
        return
    if operation is None:
        pattern = f".*{COMMITTED_TRANSACTION_MARKER_SUFFIX}"
    else:
        pattern = f".{operation}-{transaction_id}-*{COMMITTED_TRANSACTION_MARKER_SUFFIX}"
    for marker_path in sorted(root.glob(pattern)):
        if not marker_path.is_file() or is_link_like(marker_path):
            raise HarnessError(f"Content transaction completion marker is unsafe: {marker_path}")
        recover_committed_transaction_marker(skill_root, marker_path)
    if root.exists() and not any(root.iterdir()):
        root.rmdir()


def commit_content_transaction(transaction: dict[str, Any]) -> None:
    if transaction.get("transaction_mode") is None:
        commit_legacy_content_transaction(transaction)
    elif transaction.get("transaction_mode") == FILE_SET_TRANSACTION_MODE:
        commit_file_set_content_transaction(transaction)
    else:
        raise HarnessError(f"Unsupported content transaction mode: {transaction.get('transaction_mode')!r}")

def recover_content_transactions(skill_root: Path, operation: str, transaction_id: str) -> None:
    identifier = canonical_id(transaction_id, f"{operation.title()} transaction id")
    root = content_transaction_store(skill_root)
    if not root.exists():
        return
    recover_committed_transaction_markers(
        skill_root,
        operation=operation,
        transaction_id=identifier,
    )
    if not root.exists():
        return
    for transaction_root in sorted(root.glob(f"{operation}-{identifier}-*")):
        value = read_json(transaction_root / "journal.json", {})
        if not value:
            raise HarnessError(f"Content transaction has no recovery journal: {transaction_root}")
        validate_content_transaction_record(value, skill_root)
        if value.get("phase") in {"committing", "committed"}:
            commit_content_transaction(value)
        else:
            rollback_content_transaction(value)

def recover_all_content_transactions(skill_root: Path) -> None:
    root = content_transaction_store(skill_root)
    if not root.exists():
        return
    recover_committed_transaction_markers(skill_root)
    if not root.exists():
        return
    for transaction_root in sorted(root.iterdir()):
        if not transaction_root.exists():
            continue
        if transaction_root.is_file():
            raise HarnessError(f"Content transaction store contains an unknown file: {transaction_root}")
        if not transaction_root.is_dir():
            continue
        value = read_json(transaction_root / "journal.json", {})
        if not value:
            raise HarnessError(f"Content transaction has no recovery journal: {transaction_root}")
        validate_content_transaction_record(value, skill_root)
        if value.get("phase") in {"committing", "committed"}:
            commit_content_transaction(value)
        else:
            rollback_content_transaction(value)

def capture_file_snapshots(paths: Iterable[Path]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.exists() else None for path in paths}

def restore_file_snapshots(snapshots: dict[Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            if path.exists():
                path.unlink()
        else:
            atomic_write_bytes(path, content)
