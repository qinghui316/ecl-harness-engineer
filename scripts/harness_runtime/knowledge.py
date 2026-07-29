"""Read-only knowledge drift, link, citation, and entropy checks."""

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

from .core import HarnessError, file_fingerprint, is_within, read_json, run, safe_relative
from .project import primary_worktree_root, project_context, require_skill
from .transactions import guard_project_skill_read_only

def knowledge_source_location(context: dict[str, Any], source: str) -> tuple[Path, Path]:
    base = (
        primary_worktree_root(context)
        if source.startswith(".agents/reference-projects/")
        else context["project_root"]
    )
    return base / source, base

def context_source_fingerprints(context: dict[str, Any], sources: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source in sources:
        if source.startswith(("http://", "https://", "user:", "contract:", "registry:")):
            continue
        path, base = knowledge_source_location(context, source)
        if path.is_file():
            result[source] = file_fingerprint([path], base)
    return result

def markdown_has_substance(path: Path) -> bool:
    content = re.sub(r"<!--[\s\S]*?-->", "", path.read_text(encoding="utf-8", errors="replace"))
    has_heading = False
    has_body = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        if re.match(r"^#{1,6}\s+\S", stripped):
            has_heading = True
            continue
        semantic = re.sub(r"[`*_#>|\[\](){}<>=:\-]", " ", stripped)
        if re.search(r"[A-Za-z0-9\u0080-\uffff]", semantic):
            has_body = True
    return has_heading and has_body

@guard_project_skill_read_only
def knowledge_scan(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    script = skill_root / "scripts" / "check_project_wiki_stale.py"
    result = run(
        [
            sys.executable,
            str(script),
            "--skill-root",
            str(skill_root),
            "--project-root",
            str(context["project_root"]),
        ],
        check=False,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError(f"Wiki stale scan returned invalid output: {result.stdout}") from exc
    return {"read_only": True, "stale": not value.get("ok", False), **value}

def knowledge_check_internal(skill_root: Path, context: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    knowledge = skill_root / "references" / "project_wiki"
    overview = knowledge / "overview.md"
    index = read_json(knowledge / "index.json", {})
    if not overview.exists():
        findings.append({"type": "missing_l1", "path": str(overview)})
    for item in index.get("items", []):
        if not isinstance(item, dict):
            findings.append({"type": "invalid_knowledge_index_item"})
            continue
        try:
            relative_path = safe_relative(str(item.get("path", "")), "knowledge index path")
        except HarnessError as exc:
            findings.append({"type": "invalid_knowledge_path", "id": item.get("id"), "detail": str(exc)})
            continue
        path = knowledge / relative_path
        if not path.exists():
            findings.append({"type": "missing_knowledge_entry", "id": item.get("id"), "path": str(path)})
        if str(relative_path).replace("\\", "/").startswith("bridges/") and not item.get("sources"):
            findings.append({"type": "uncited_l3_bridge", "id": item.get("id"), "path": str(relative_path)})
        for source in item.get("sources", []):
            if not isinstance(source, str):
                findings.append({"type": "invalid_knowledge_source", "id": item.get("id")})
                continue
            if source.startswith(("http://", "https://", "user:", "contract:", "registry:")):
                continue
            try:
                source = safe_relative(source, "knowledge source")
            except HarnessError as exc:
                findings.append({"type": "invalid_knowledge_source", "id": item.get("id"), "detail": str(exc)})
                continue
            source_path, source_root = knowledge_source_location(context, source)
            if not is_within(source_path.resolve(), source_root):
                findings.append({"type": "external_knowledge_source", "id": item.get("id"), "source": source})
            elif not source_path.exists():
                findings.append({"type": "missing_knowledge_source", "id": item.get("id"), "source": source})
        for source, expected in item.get("source_fingerprints", {}).items():
            if not isinstance(source, str) or not isinstance(expected, str):
                findings.append({"type": "invalid_knowledge_fingerprint", "id": item.get("id")})
                continue
            try:
                source = safe_relative(source, "knowledge fingerprint source")
            except HarnessError as exc:
                findings.append({"type": "invalid_knowledge_source", "id": item.get("id"), "detail": str(exc)})
                continue
            path_source, source_root = knowledge_source_location(context, source)
            if not is_within(path_source.resolve(), source_root):
                findings.append({"type": "external_knowledge_source", "id": item.get("id"), "source": source})
                continue
            if path_source.is_file():
                current = file_fingerprint([path_source], source_root)
                if current != expected:
                    findings.append({"type": "knowledge_drift", "id": item.get("id"), "source": source})
        if path.exists() and path.suffix == ".md":
            content = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)", content):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (path.parent / target).resolve()
                if not is_within(resolved, knowledge):
                    findings.append({"type": "external_knowledge_link", "id": item.get("id"), "target": target})
                elif not resolved.exists():
                    findings.append({"type": "broken_knowledge_link", "id": item.get("id"), "target": target})
    for folder in (
        knowledge / "modules", knowledge / "systems", knowledge / "bridges",
        knowledge / "reference_projects" / "maps",
    ):
        if folder.exists():
            for path in folder.glob("*.md"):
                if not markdown_has_substance(path):
                    findings.append({"type": "empty_knowledge_entry", "path": str(path)})
    review_files = [path for path in knowledge.rglob("*.md") if path.is_file()]
    project_root = context["project_root"]
    for pattern in ("AGENTS.md", "CLAUDE.md", "STATUS*.md", "CURRENT*.md"):
        review_files.extend(path for path in project_root.glob(pattern) if path.is_file())
    normalized: dict[str, list[str]] = {}
    archive_lines: list[str] = []
    current_fact_files: set[str] = set()
    for path in dict.fromkeys(review_files):
        relative = str(path.relative_to(project_root)) if is_within(path, project_root) else str(path.relative_to(skill_root))
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            compact = re.sub(r"[`*_#>|\[\](){}]", " ", line.lower())
            compact = re.sub(r"\s+", " ", compact).strip()
            is_current_fact = bool(re.search(
                r"current (?:baseline|status|plan|roadmap)|next action|latest completed|active change|pending integration",
                compact,
            ))
            if len(compact) >= 30 and is_current_fact:
                normalized.setdefault(compact, []).append(relative)
            if re.search(r"latest completed|changes/archive|archive/[^ ]+", compact):
                archive_lines.append(f"{relative}: {line.strip()[:180]}")
            if is_current_fact:
                current_fact_files.add(relative)
    duplicates = [
        {"text": line[:180], "owners": sorted(set(owners))}
        for line, owners in normalized.items() if len(set(owners)) > 1
    ]
    if duplicates:
        warnings.append({"type": "duplicate_current_fact_candidates", "count": len(duplicates), "examples": duplicates[:10]})
    if archive_lines:
        warnings.append({"type": "archive_ledger_leakage", "count": len(archive_lines), "examples": archive_lines[:10]})
    if len(current_fact_files) > 1:
        warnings.append({"type": "multiple_current_state_owners", "owners": sorted(current_fact_files)})
    roadmap_owners = [item for item in current_fact_files if "plan" in item.lower() or "roadmap" in item.lower()]
    status_owners = [item for item in current_fact_files if "status" in item.lower() or "agents.md" in item.lower()]
    if roadmap_owners and status_owners:
        warnings.append({
            "type": "roadmap_current_state_conflict",
            "roadmap_owners": sorted(roadmap_owners),
            "current_state_owners": sorted(status_owners),
        })
    repairs = {
        "broken_knowledge_link": "Repair the project-Wiki link or remove the unsupported projection through migrate/E1.",
        "uncited_l3_bridge": "Add canonical evidence for every L3 mapping or retire the bridge through migrate/E1.",
        "knowledge_drift": "Rescan the affected source and replan against Registry/canonical facts before refreshing Wiki.",
        "duplicate_current_fact_candidates": "Choose one current-fact owner and classify duplicate text as retain/merge/retire/archive-only.",
        "archive_ledger_leakage": "Keep archive detail behind INDEX/summary links instead of default-loaded current pages.",
        "multiple_current_state_owners": "Assign one owner for current status and make other documents route to it.",
        "roadmap_current_state_conflict": "Keep roadmap and current status in distinct owners and remove repeated current claims.",
    }
    for severity, items in (("error", findings), ("warning", warnings)):
        for item in items:
            item.setdefault("severity", severity)
            item.setdefault("owner", "project Harness knowledge/audit owner")
            item.setdefault("location", item.get("path") or item.get("id") or "project knowledge graph")
            item.setdefault("reason", item["type"].replace("_", " "))
            item.setdefault("repair", repairs.get(item["type"], "Rescan evidence and repair through init, migrate, or accepted E1 Evolution."))
    return {
        "healthy": not findings,
        "findings": findings,
        "warnings": warnings,
        "items": len(index.get("items", [])),
    }

@guard_project_skill_read_only
def knowledge_check(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    return knowledge_check_internal(skill_root, context)
