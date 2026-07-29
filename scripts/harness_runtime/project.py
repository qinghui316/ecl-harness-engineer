"""Project identity, Git/worktree discovery, canonical Skill paths, and manifests."""

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

from .core import EVOLUTION_THRESHOLD, HarnessError, SCHEMA_VERSION, atomic_write_json, atomic_write_text, git, git_value, is_link_like, normalize_path, read_json, reject_linked_ancestors, slugify, stable_hash, utc_now

def project_context(project_root: Path) -> dict[str, Any]:
    lexical_request = Path(os.path.abspath(project_root))
    if is_link_like(lexical_request):
        raise HarnessError(f"Project root must be a physical directory, not a link: {lexical_request}")
    requested = lexical_request.resolve()
    if not requested.exists() or not requested.is_dir():
        raise HarnessError(f"Project root does not exist or is not a directory: {requested}")
    top = git_value(requested, "rev-parse", "--show-toplevel")
    if top:
        root = Path(top).resolve()
        common_raw = git_value(root, "rev-parse", "--git-common-dir")
        if not common_raw:
            raise HarnessError("Git repository has no resolvable common dir.")
        common = Path(common_raw)
        if not common.is_absolute():
            common = (root / common).resolve()
        identity_source = normalize_path(common)
        mode = "multi_lane"
        branch = git_value(root, "branch", "--show-current")
        head = git_value(root, "rev-parse", "HEAD")
    else:
        root = requested
        common = None
        identity_source = normalize_path(root)
        mode = "single_lane"
        branch = None
        head = None
    if common is not None:
        repository_name = common.parent.name if common.name == ".git" else common.name
    else:
        repository_name = root.name
    name = slugify(repository_name)
    project_id = f"{name}-{stable_hash(identity_source)}"
    return {
        "project_root": root,
        "project_name": name,
        "project_id": project_id,
        "skill_name": f"{project_id}-harness",
        "git_common_dir": common,
        "mode": mode,
        "branch": branch,
        "head": head,
    }

def canonical_branch_and_commit(context: dict[str, Any], requested: str | None = None) -> tuple[str | None, str | None]:
    if context["mode"] == "single_lane":
        return None, None
    root: Path = context["project_root"]
    candidates: list[str] = []
    if requested:
        candidates.append(requested)
    remote_head = git_value(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if remote_head and "/" in remote_head:
        candidates.append(remote_head.split("/", 1)[1])
    candidates.extend(["main", "master", "trunk"])
    if context.get("branch"):
        candidates.append(context["branch"])
    for branch in dict.fromkeys(candidates):
        commit = git_value(root, "rev-parse", "--verify", f"refs/heads/{branch}")
        if commit:
            return branch, commit
    return context.get("branch"), context.get("head")

def worktree_roots(context: dict[str, Any]) -> list[Path]:
    if context["mode"] == "single_lane":
        return [context["project_root"]]
    result = git(context["project_root"], "worktree", "list", "--porcelain", check=False)
    roots: list[Path] = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                candidate = Path(line.removeprefix("worktree ").strip()).resolve()
                if candidate.is_dir():
                    roots.append(candidate)
    if not roots:
        roots.append(context["project_root"])
    return list(dict.fromkeys(roots))

def primary_worktree_root(context: dict[str, Any]) -> Path:
    if context["mode"] == "single_lane":
        return context["project_root"]
    common: Path = context["git_common_dir"]
    if common.name == ".git" and common.parent.is_dir():
        return common.parent.resolve()
    return worktree_roots(context)[0]

def local_root(context: dict[str, Any], args: argparse.Namespace) -> Path:
    del args
    primary = primary_worktree_root(context)
    root = primary / ".agents" / "skills"
    reject_linked_ancestors(primary, root, "Project Harness discovery path")
    return root

def skill_root_for(context: dict[str, Any], args: argparse.Namespace) -> Path:
    return local_root(context, args) / context["skill_name"]

def require_skill(context: dict[str, Any], args: argparse.Namespace) -> Path:
    root = skill_root_for(context, args)
    if is_link_like(root):
        raise HarnessError(f"Canonical project Harness must be a physical directory: {root}")
    manifest = read_json(root / "state" / "manifest.json")
    if not manifest:
        raise HarnessError(
            f"Project Harness Skill is not initialized: {root}. Run project init first."
        )
    if manifest.get("project_id") != context["project_id"]:
        raise HarnessError("Project id does not match the local Harness manifest.")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError("Project Harness manifest schema does not match this runtime.")
    if manifest.get("mode") != context["mode"]:
        raise HarnessError("Project mode does not match the local Harness manifest.")
    if root.name != context["skill_name"]:
        raise HarnessError("Project Harness directory name does not match project identity.")
    if normalize_path(Path(manifest.get("project_root", "."))) != normalize_path(primary_worktree_root(context)):
        raise HarnessError("Project root does not match the local Harness manifest.")
    expected_common = context.get("git_common_dir")
    recorded_common = manifest.get("git_common_dir")
    if bool(expected_common) != bool(recorded_common) or (
        expected_common and normalize_path(Path(recorded_common)) != normalize_path(expected_common)
    ):
        raise HarnessError("Git common dir does not match the local Harness manifest.")
    return root

def initial_manifest(
    context: dict[str, Any],
    links: list[dict[str, str]],
    launchers: list[str],
) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": context["project_id"],
        "project_name": context["project_name"],
        "project_root": str(primary_worktree_root(context)),
        "git_common_dir": str(context["git_common_dir"]) if context["git_common_dir"] else None,
        "mode": context["mode"],
        "skill_revision": 1,
        "host_runtime": "python",
        "host_command": str(Path(sys.executable).resolve()),
        "launchers": launchers,
        "created_at": now,
        "updated_at": now,
        "runtime_links": links,
    }

def ensure_state(skill_root: Path, context: dict[str, Any], canonical_branch: str | None = None) -> None:
    state = skill_root / "state"
    for relative in (
        "registry/lanes", "registry/changes", "registry/contracts", "registry/integrations",
        "registry/locks", "registry/baseline-events", "evolution/proposals", "evolution/staging",
        "changes/active", "changes/parking", "changes/archive", "analysis", "migration",
    ):
        (state / relative).mkdir(parents=True, exist_ok=True)
    branch, commit = canonical_branch_and_commit(context, canonical_branch)
    baseline = {
        "schema_version": SCHEMA_VERSION,
        "canonical_root": str(primary_worktree_root(context)),
        "canonical_branch": branch,
        "canonical_commit": commit,
        "updated_at": utc_now(),
    }
    atomic_write_json(state / "registry" / "baseline.json", baseline)
    evolution = {
        "schema_version": SCHEMA_VERSION,
        "threshold": EVOLUTION_THRESHOLD,
        "evaluated_change_ids": [],
        "pending_change_ids": [],
        "pending": False,
        "last_completed_at": None,
    }
    atomic_write_json(state / "evolution" / "state.json", evolution)
    results = state / "evolution" / "results.tsv"
    if not results.exists():
        atomic_write_text(
            results,
            "timestamp\tproposal_id\tchange_ids\tscore\tstatus\teval_mode\tnote",
        )
    atomic_write_json(
        state / "changes" / "INDEX.json",
        {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "changes": []},
    )
