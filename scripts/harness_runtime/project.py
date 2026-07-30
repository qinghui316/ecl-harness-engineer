"""Project identity, Git/worktree discovery, canonical Skill paths, and manifests."""

from __future__ import annotations

import argparse
import os
import re
import secrets
from pathlib import Path
from typing import Any

from .core import EVOLUTION_THRESHOLD, HarnessError, MANIFEST_SCHEMA_VERSION, SCHEMA_VERSION, atomic_write_json, atomic_write_text, canonical_id, git, git_value, is_link_like, read_json, reject_linked_ancestors, slugify, utc_now


PROJECT_ID_MARKER = re.compile(r"<!-- ECL-HARNESS-PROJECT-ID:\s*([a-z0-9-]+)\s*-->")


def assign_project_identity(context: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    identifier = canonical_id(
        project_id or f"{context['project_name']}-{secrets.token_hex(6)}",
        "Project id",
    )
    context["project_id"] = identifier
    context["skill_name"] = f"{identifier}-harness"
    return context


def route_project_ids(context: dict[str, Any]) -> set[str]:
    roots = [context["project_root"]]
    primary = primary_worktree_root(context)
    if primary not in roots:
        roots.append(primary)
    identifiers: set[str] = set()
    for root in roots:
        for name in ("AGENTS.md", "CLAUDE.md"):
            path = root / name
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            marked = PROJECT_ID_MARKER.findall(content)
            identifiers.update(marked)
            if not marked:
                for skill_name in re.findall(r"`([a-z0-9-]+-harness)`", content):
                    identifiers.add(skill_name.removesuffix("-harness"))
    return identifiers


def discover_project_identity(context: dict[str, Any]) -> dict[str, Any]:
    identifiers = route_project_ids(context)
    if len(identifiers) > 1:
        raise HarnessError(f"Project routes contain conflicting Harness project ids: {sorted(identifiers)}")
    if identifiers:
        assign_project_identity(context, next(iter(identifiers)))
    return context

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
        mode = "multi_lane"
        branch = git_value(root, "branch", "--show-current")
        head = git_value(root, "rev-parse", "HEAD")
    else:
        root = requested
        common = None
        mode = "single_lane"
        branch = None
        head = None
    if common is not None:
        repository_name = common.parent.name if common.name == ".git" else common.name
    else:
        repository_name = root.name
    name = slugify(repository_name)
    context = {
        "project_root": root,
        "project_name": name,
        "project_id": None,
        "skill_name": None,
        "git_common_dir": common,
        "mode": mode,
        "branch": branch,
        "head": head,
    }
    return discover_project_identity(context)

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
    if not context.get("skill_name"):
        discover_project_identity(context)
    if not context.get("skill_name"):
        raise HarnessError("No project Harness identity marker was found. Run project init first.")
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
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise HarnessError("Project Harness manifest schema does not match this runtime.")
    if root.name != context["skill_name"]:
        raise HarnessError("Project Harness directory name does not match project identity.")
    if manifest.get("skill_name") != context["skill_name"]:
        raise HarnessError("Project Harness manifest skill name does not match the project route.")
    return root

def initial_manifest(
    context: dict[str, Any],
    links: list[dict[str, str]],
    launchers: list[str],
) -> dict[str, Any]:
    del links
    now = utc_now()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project_id": context["project_id"],
        "project_name": context["project_name"],
        "skill_name": context["skill_name"],
        "skill_revision": 1,
        "launchers": launchers,
        "created_at": now,
        "updated_at": now,
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
