"""Read-only knowledge drift, link, citation, and entropy checks."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

from .core import HarnessError, git, git_value, is_within, read_json, safe_relative
from .project import primary_worktree_root, project_context, require_skill
from .transactions import guard_project_skill_read_only

NON_LOCAL_EVIDENCE_PREFIXES = ("http://", "https://", "user:", "contract:", "registry:")
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")

def knowledge_source_location(context: dict[str, Any], source: str) -> tuple[Path, Path]:
    if source.startswith(".agents/reference-projects/"):
        parts = Path(source).parts
        if len(parts) < 4:
            return primary_worktree_root(context) / source, primary_worktree_root(context)
        primary = primary_worktree_root(context)
        base = primary / Path(*parts[:3])
        return primary / source, base
    else:
        base = context["project_root"]
    return base / source, base


def source_fingerprint(path: Path, source_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = source_root.resolve()
    if not is_within(resolved_path, resolved_root):
        raise HarnessError(f"Knowledge source resolves outside its evidence root: {path}")

    git_root_value = git_value(resolved_path.parent, "rev-parse", "--show-toplevel")
    if git_root_value:
        git_root = Path(git_root_value).resolve()
        if is_within(resolved_path, git_root):
            relative = resolved_path.relative_to(git_root).as_posix()
            tracked = git(git_root, "ls-files", "--error-unmatch", "--", relative, check=False)
            if tracked.returncode == 0:
                hashed = git(
                    git_root, "hash-object", f"--path={relative}", str(resolved_path), check=False,
                )
                blob = hashed.stdout.strip()
                if hashed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", blob):
                    payload = relative.encode("utf-8") + b"\0git:" + blob.encode("ascii")
                    return hashlib.sha256(payload).hexdigest()

    relative = resolved_path.relative_to(resolved_root).as_posix()
    content = resolved_path.read_bytes()
    if b"\0" not in content[:8192]:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            content = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(relative.encode("utf-8") + b"\0" + content).hexdigest()

def context_source_fingerprints(context: dict[str, Any], sources: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source in sources:
        if source.startswith(NON_LOCAL_EVIDENCE_PREFIXES):
            continue
        path, base = knowledge_source_location(context, source)
        if path.is_file():
            result[source] = source_fingerprint(path, base)
    return result

def knowledge_fingerprint_scan(
    skill_root: Path,
    context: dict[str, Any],
    selected_sources: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    index_path = skill_root / "references" / "project_wiki" / "index.json"
    index = read_json(index_path, None)
    if not isinstance(index, dict) or not isinstance(index.get("items"), list):
        raise HarnessError(f"Invalid project knowledge index: {index_path}")

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    source_results: dict[str, tuple[str, str | None]] = {}
    checked = 0

    def add(finding_type: str, item_id: Any, source: Any, **detail: Any) -> None:
        key = (finding_type, str(item_id or ""), str(source or ""))
        if key in seen:
            return
        seen.add(key)
        findings.append({"type": finding_type, "item": item_id, "source": source, **detail})

    for item in index["items"]:
        if not isinstance(item, dict):
            add("invalid_source", None, None, detail="knowledge index item must be an object")
            continue
        item_id = item.get("id")
        selected_for_item = None if selected_sources is None else selected_sources.get(str(item_id or ""))
        if selected_sources is not None and selected_for_item is None:
            continue
        fingerprints = item.get("source_fingerprints", {})
        if not isinstance(fingerprints, dict):
            add("invalid_fingerprint", item_id, None, detail="source_fingerprints must be an object")
            continue
        for raw_source, expected in fingerprints.items():
            if not isinstance(raw_source, str) or not raw_source.strip():
                add("invalid_source", item_id, raw_source, detail="source must be a non-empty string")
                continue
            if raw_source.startswith(NON_LOCAL_EVIDENCE_PREFIXES):
                continue
            try:
                source = safe_relative(raw_source, "knowledge fingerprint source")
            except HarnessError as exc:
                add("invalid_source", item_id, raw_source, detail=str(exc))
                continue
            if selected_for_item is not None and source not in selected_for_item:
                continue
            if not isinstance(expected, str) or not FINGERPRINT_PATTERN.fullmatch(expected):
                add("invalid_fingerprint", item_id, source, expected=expected)
                continue
            checked += 1
            if source not in source_results:
                source_path, source_root = knowledge_source_location(context, source)
                resolved_root = source_root.resolve()
                resolved_source = source_path.resolve()
                if not is_within(resolved_source, resolved_root):
                    source_results[source] = ("outside_project", None)
                elif not source_path.is_file():
                    source_results[source] = ("missing", None)
                else:
                    source_results[source] = ("current", source_fingerprint(source_path, source_root))
            status, current = source_results[source]
            if status == "outside_project":
                add("outside_project", item_id, source, expected=expected)
            elif status == "missing":
                add("missing", item_id, source, expected=expected, current=None)
            elif current != expected:
                add("changed", item_id, source, expected=expected, current=current)

    return {
        "read_only": True,
        "healthy": not findings,
        "stale": bool(findings),
        "checked": checked,
        "unique_sources": len(source_results),
        "findings": findings,
    }

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
    return knowledge_fingerprint_scan(skill_root, context)

def knowledge_check_internal(skill_root: Path, context: dict[str, Any]) -> dict[str, Any]:
    fingerprint_scan = knowledge_fingerprint_scan(skill_root, context)
    fingerprint_types = {
        "changed": "knowledge_drift",
        "missing": "missing_knowledge_source",
        "invalid_source": "invalid_knowledge_source",
        "outside_project": "external_knowledge_source",
        "invalid_fingerprint": "invalid_knowledge_fingerprint",
    }
    findings: list[dict[str, Any]] = [
        {
            **item,
            "type": fingerprint_types[item["type"]],
            "id": item.get("item"),
        }
        for item in fingerprint_scan["findings"]
    ]
    finding_keys = {
        (item.get("type"), item.get("id"), item.get("source"))
        for item in findings
    }
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
            if source.startswith(NON_LOCAL_EVIDENCE_PREFIXES):
                continue
            try:
                source = safe_relative(source, "knowledge source")
            except HarnessError as exc:
                findings.append({"type": "invalid_knowledge_source", "id": item.get("id"), "detail": str(exc)})
                continue
            source_path, source_root = knowledge_source_location(context, source)
            if not is_within(source_path.resolve(), source_root):
                key = ("external_knowledge_source", item.get("id"), source)
                if key not in finding_keys:
                    findings.append({"type": key[0], "id": key[1], "source": key[2]})
                    finding_keys.add(key)
            elif not source_path.exists():
                key = ("missing_knowledge_source", item.get("id"), source)
                if key not in finding_keys:
                    findings.append({"type": key[0], "id": key[1], "source": key[2]})
                    finding_keys.add(key)
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
    normalized: dict[str, list[str]] = {}
    archive_lines: list[str] = []
    current_fact_files: set[str] = set()
    roadmap_fact_files: set[str] = set()
    status_fact_files: set[str] = set()
    for path in dict.fromkeys(review_files):
        relative = str(path.relative_to(skill_root))
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
                if re.search(r"current plan|roadmap|next action", compact):
                    roadmap_fact_files.add(relative)
                if re.search(r"current status|current baseline|latest completed|pending integration", compact):
                    status_fact_files.add(relative)
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
    roadmap_owners = sorted(roadmap_fact_files)
    status_owners = sorted(status_fact_files)
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
        "read_only": True,
        "healthy": not findings,
        "stale": not fingerprint_scan["healthy"],
        "checked": fingerprint_scan["checked"],
        "unique_sources": fingerprint_scan["unique_sources"],
        "findings": findings,
        "warnings": warnings,
        "items": len(index.get("items", [])),
    }

@guard_project_skill_read_only
def knowledge_check(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    return knowledge_check_internal(skill_root, context)
