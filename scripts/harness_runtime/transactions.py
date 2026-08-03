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
    atomic_write_json(transaction_root / "journal.json", value)

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

def validate_content_transaction_record(
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

def rollback_content_transaction(transaction: dict[str, Any]) -> None:
    validate_content_transaction_record(transaction)
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

def apply_content_transaction(
    skill_root: Path,
    candidate: Path,
    operation: str,
    transaction_id: str,
    *,
    state_snapshot_paths: Iterable[Path] = (),
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
    sidecars = repository_sidecars(skill_root)
    transaction_root = content_transaction_store(skill_root) / f"{operation}-{identifier}-{secrets.token_hex(8)}"
    transaction_root.mkdir(parents=True, exist_ok=False)
    replacement = transaction_root / "next"
    backup = transaction_root / "previous"
    original_analysis = transaction_root / "original-analysis"
    candidate_analysis = transaction_root / "candidate-analysis"
    replacement.mkdir()
    for relative in CONTENT_TRANSACTION_PATHS:
        source = candidate / relative
        if path_present(source):
            copy_transaction_path(source, replacement / relative)
    if path_present(candidate / "state" / "analysis"):
        copy_transaction_path(candidate / "state" / "analysis", candidate_analysis)
    state_snapshots: dict[str, dict[str, Any]] = {}
    for snapshot_path in state_snapshot_paths:
        resolved = snapshot_path.resolve()
        if not is_within(resolved, skill_root):
            raise HarnessError(f"Transaction state snapshot is outside the project Harness: {snapshot_path}")
        relative = resolved.relative_to(skill_root.resolve()).as_posix()
        backup_path = transaction_root / "state-snapshots" / relative
        present = snapshot_path.is_file()
        if present:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snapshot_path, backup_path)
        state_snapshots[relative] = {"present": present, "path": str(backup_path)}
    transaction = {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "transaction_id": identifier,
        "skill_root": str(skill_root),
        "candidate": str(candidate),
        "transaction_root": str(transaction_root),
        "replacement": str(replacement),
        "backup": str(backup),
        "original_analysis": str(original_analysis),
        "state_snapshots": state_snapshots,
        "repository_sidecars": sidecars,
        "phase": "prepared",
        "created_at": utc_now(),
    }
    transaction_journal(transaction_root, transaction)
    try:
        transaction_move(skill_root, backup)
        transaction["phase"] = "current_moved"
        transaction_journal(transaction_root, transaction)
        if not path_present(backup / "state"):
            raise HarnessError("Current project Harness has no state directory to preserve.")
        transaction_move(backup / "state", replacement / "state")
        transaction["phase"] = "state_preserved"
        transaction_journal(transaction_root, transaction)
        for relative in sidecars:
            source = backup / relative
            if path_present(source):
                transaction_move(source, replacement / relative)
        transaction["phase"] = "repository_sidecars_preserved"
        transaction_journal(transaction_root, transaction)
        if path_present(candidate_analysis):
            if path_present(replacement / "state" / "analysis"):
                transaction_move(replacement / "state" / "analysis", original_analysis)
            transaction_move(candidate_analysis, replacement / "state" / "analysis")
        transaction["phase"] = "analysis_applied"
        transaction_journal(transaction_root, transaction)
        transaction_move(replacement, skill_root)
        transaction["phase"] = "published"
        transaction_journal(transaction_root, transaction)
        return transaction
    except Exception as exc:
        rollback_content_transaction(transaction)
        if isinstance(exc, HarnessError):
            raise
        raise HarnessError(f"{operation.title()} content transaction failed: {exc}") from exc

def commit_content_transaction(transaction: dict[str, Any]) -> None:
    validate_content_transaction_record(transaction)
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

def recover_content_transactions(skill_root: Path, operation: str, transaction_id: str) -> None:
    identifier = canonical_id(transaction_id, f"{operation.title()} transaction id")
    root = content_transaction_store(skill_root)
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
    for transaction_root in sorted(root.iterdir()):
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
