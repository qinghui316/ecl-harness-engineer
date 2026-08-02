"""ECL Change evidence, INDEX, lifecycle, preflight, contracts, and evolution eligibility."""

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

from .contracts import validate_change_evidence
from .core import EVOLUTION_THRESHOLD, HarnessError, REQUIRED_CHANGE_FILES, SCHEMA_VERSION, TERMINAL_CHANGE_STATUSES, _UNSET, atomic_create_json, atomic_write_json, atomic_write_text, canonical_id, git, git_baseline_relation, git_value, is_link_like, read_json, reject_tree_links, remove_owned_tree, render, safe_relative, slugify, utc_now
from .knowledge import KNOWLEDGE_BASELINE_FILE, discover_project_knowledge, knowledge_fingerprint_scan, rebuild_project_wiki_catalog
from .project import project_context, require_skill
from .registry import bound_records, lane_id, registry_root
from .transactions import guard_project_skill, short_registry_lock

def changes_root(skill_root: Path) -> Path:
    return skill_root / "state" / "changes"

def change_evidence_dir(skill_root: Path, state: str, change_id: str) -> Path:
    if state not in {"active", "parking", "archive"}:
        raise HarnessError(f"Unsupported Change evidence state: {state}")
    return changes_root(skill_root) / state / canonical_id(change_id, "Change id")

def active_change_dir(skill_root: Path, change_id: str) -> Path:
    return change_evidence_dir(skill_root, "active", change_id)

def parking_change_dir(skill_root: Path, change_id: str) -> Path:
    return change_evidence_dir(skill_root, "parking", change_id)

def archive_change_dir(skill_root: Path, change_id: str) -> Path:
    return change_evidence_dir(skill_root, "archive", change_id)

def locate_change_evidence(skill_root: Path, change_id: str) -> tuple[str, Path] | tuple[None, None]:
    for state in ("active", "parking", "archive"):
        path = change_evidence_dir(skill_root, state, change_id)
        if path.is_dir():
            if is_link_like(path):
                raise HarnessError(f"Change evidence directory must be physical: {path}")
            return state, path
    return None, None

def require_physical_change_evidence(path: Path, label: str) -> None:
    if not path.is_dir() or is_link_like(path):
        raise HarnessError(f"{label} must be a physical Change evidence directory: {path}")
    reject_tree_links(path, label)

def summary_metadata(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {"modules": [], "paths": [], "tags": [], "decisions": [], "validation": []}
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        header, body = text[4:].split("\n---\n", 1)
        for line in header.splitlines():
            match = re.match(r"^(modules|paths|tags):\s*\[(.*)\]\s*$", line.strip())
            if match:
                values = [item.strip().strip("\"'") for item in match.group(2).split(",") if item.strip()]
                metadata[match.group(1)] = values
    else:
        body = text
    section = None
    for line in body.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if line.strip().startswith("- ") and section == "decisions":
            value = line.strip()[2:].strip()
            if value and value.lower() not in {"pending.", "none recorded."}:
                metadata["decisions"].append(value)
        if line.strip().startswith("- ") and section == "validation":
            value = line.strip()[2:].strip()
            if value and "tbd" not in value.lower():
                metadata["validation"].append(value)
    return metadata

def change_index_entry(skill_root: Path, value: dict[str, Any]) -> dict[str, Any]:
    change_id = canonical_id(value.get("change_id", ""), "Change id")
    evidence_state, evidence_path = locate_change_evidence(skill_root, change_id)
    summary = ""
    if evidence_path and (evidence_path / "summary.md").is_file():
        summary = (evidence_path / "summary.md").read_text(encoding="utf-8", errors="replace")
    metadata = summary_metadata(summary)
    return {
        "change_id": change_id,
        "lane_id": value.get("lane_id"),
        "status": value.get("status"),
        "evidence_state": evidence_state,
        "scope": value.get("scope", ""),
        "modules": sorted(set(value.get("modules", [])) | set(metadata["modules"])),
        "paths": sorted(set(value.get("paths", [])) | set(metadata["paths"])),
        "tags": sorted(set(value.get("tags", [])) | set(metadata["tags"])),
        "decisions": metadata["decisions"],
        "validation": metadata["validation"],
        "validation_passed": value.get("validation_passed", False),
        "base_commit": value.get("base_commit"),
        "completion_commit": value.get("completion_commit"),
        "summary_path": (
            (evidence_path / "summary.md").relative_to(skill_root).as_posix()
            if evidence_path else None
        ),
        "summary_excerpt": " ".join(summary.split())[:500],
        "updated_at": value.get("updated_at"),
    }

def computed_change_index(skill_root: Path) -> dict[str, Any]:
    entries = [change_index_entry(skill_root, value) for value in change_records(skill_root)]
    entries.sort(key=lambda item: (item.get("updated_at") or "", item["change_id"]), reverse=True)
    return {"schema_version": SCHEMA_VERSION, "changes": entries}

def rebuild_change_index(skill_root: Path) -> dict[str, Any]:
    index = {**computed_change_index(skill_root), "generated_at": utc_now()}
    atomic_write_json(changes_root(skill_root) / "INDEX.json", index)
    return index

def ecl_integrity_findings(skill_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        changes = change_records(skill_root)
        lanes = bound_records(registry_root(skill_root) / "lanes", "lane_id", "Lane")
    except (HarnessError, OSError, json.JSONDecodeError) as exc:
        return [{"type": "invalid_registry_record", "detail": str(exc)}]
    by_id = {item["change_id"]: item for item in changes}
    evidence_ids: dict[str, str] = {}
    for state in ("active", "parking", "archive"):
        folder = changes_root(skill_root) / state
        if not folder.exists():
            findings.append({"type": "missing_change_state_directory", "state": state})
            continue
        for path in sorted(item for item in folder.iterdir() if item.is_dir()):
            try:
                identifier = canonical_id(path.name, "Change evidence id")
            except HarnessError as exc:
                findings.append({"type": "invalid_change_evidence_id", "path": str(path), "detail": str(exc)})
                continue
            if identifier in evidence_ids:
                findings.append({"type": "duplicate_change_evidence", "change_id": identifier})
            evidence_ids[identifier] = state
            if identifier not in by_id:
                findings.append({"type": "orphan_change_evidence", "change_id": identifier, "state": state})
    terminal = {"completed", "blocked", "abandoned"}
    for identifier, record in by_id.items():
        evidence_state = evidence_ids.get(identifier)
        expected = "archive" if record.get("status") in terminal else (
            "parking" if record.get("status") == "parking" else "active"
        )
        if evidence_state != expected:
            findings.append({
                "type": "change_evidence_state_mismatch", "change_id": identifier,
                "record_status": record.get("status"), "expected": expected, "actual": evidence_state,
            })
        if evidence_state:
            evidence_path = change_evidence_dir(skill_root, evidence_state, identifier)
            valid, issues = validate_change_evidence(evidence_path)
            if record.get("evidence_complete") and not valid:
                findings.append({"type": "tampered_change_evidence", "change_id": identifier, "issues": issues})
    for lane in lanes:
        active_id = lane.get("active_change_id")
        if active_id:
            record = by_id.get(active_id)
            if not record or record.get("lane_id") != lane.get("lane_id") or record.get("status") not in {"planning", "active"}:
                findings.append({"type": "lane_active_change_mismatch", "lane_id": lane.get("lane_id"), "change_id": active_id})
    index = read_json(changes_root(skill_root) / "INDEX.json", {})
    expected_index = computed_change_index(skill_root)
    actual_index = {"schema_version": index.get("schema_version"), "changes": index.get("changes")}
    if actual_index != expected_index:
        findings.append({"type": "stale_or_tampered_change_index"})
    return findings

def ensure_lane(
    skill_root: Path,
    context: dict[str, Any],
    active_change_id: str | None | object = _UNSET,
) -> dict[str, Any]:
    identifier = lane_id(context)
    path = registry_root(skill_root) / "lanes" / f"{identifier}.json"
    current = read_json(path, {})
    resolved_active = current.get("active_change_id") if active_change_id is _UNSET else active_change_id
    value = {
        "schema_version": SCHEMA_VERSION,
        "lane_id": identifier,
        "branch": context["branch"],
        "head_commit": context["head"],
        "active_change_id": resolved_active,
        "status": "active" if resolved_active else "idle",
        "updated_at": utc_now(),
    }
    atomic_write_json(path, value)
    return value

def change_record_path(skill_root: Path, change_id: str) -> Path:
    identifier = canonical_id(change_id, "Change id")
    return registry_root(skill_root) / "changes" / f"{identifier}.json"

def contract_record_path(skill_root: Path, change_id: str) -> Path:
    identifier = canonical_id(change_id, "Change id")
    return registry_root(skill_root) / "contracts" / f"{identifier}.json"

def load_change_record(skill_root: Path, change_id: str, *, required: bool = False) -> dict[str, Any]:
    identifier = canonical_id(change_id, "Change id")
    value = read_json(change_record_path(skill_root, identifier), {})
    if not value:
        if required:
            raise HarnessError(f"Unknown Change: {identifier}")
        return {}
    if not isinstance(value, dict) or value.get("change_id") != identifier:
        raise HarnessError(f"Change record id mismatch: {identifier}")
    return value

def load_contract_record(skill_root: Path, change_id: str) -> dict[str, Any]:
    identifier = canonical_id(change_id, "Change id")
    value = read_json(contract_record_path(skill_root, identifier), {})
    if not value:
        return {}
    if not isinstance(value, dict) or value.get("change_id") != identifier:
        raise HarnessError(f"Contract record id mismatch: {identifier}")
    return value

def change_records(skill_root: Path) -> list[dict[str, Any]]:
    return bound_records(registry_root(skill_root) / "changes", "change_id", "Change")

def contract_records(skill_root: Path) -> list[dict[str, Any]]:
    return bound_records(registry_root(skill_root) / "contracts", "change_id", "Contract")

def require_change_owner(context: dict[str, Any], value: dict[str, Any]) -> None:
    if value.get("lane_id") != lane_id(context):
        raise HarnessError("Only the owning Lane may mutate this Change.")

def copy_change_templates(skill_root: Path, target: Path, change_id: str) -> None:
    templates = skill_root / "assets" / "templates"
    mapping = {
        "summary.md": "summary.md", "spec.md": "spec.md", "plan.md": "plan.md",
        "tasks.md": "tasks.md", "review.md": "reviews/review.md",
    }
    for source_name, target_name in mapping.items():
        content = templates.joinpath(source_name).read_text(encoding="utf-8")
        atomic_write_text(target / target_name, render(content, {"CHANGE_ID": change_id}))

@guard_project_skill
def change_new(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    change_id = canonical_id(args.change_id, "Change id")
    existing = change_records(skill_root)
    if context["mode"] == "single_lane" and any(item.get("status") in {"planning", "active"} for item in existing):
        raise HarnessError("Single-Lane mode already has an active Change.")
    current_lane_id = lane_id(context)
    if any(
        item.get("lane_id") == current_lane_id and item.get("status") in {"planning", "active"}
        for item in existing
    ):
        raise HarnessError("This Lane already has an active Change.")
    target = active_change_dir(skill_root, change_id)
    if target.exists():
        raise HarnessError(f"Active Change directory already exists: {target}")
    identifier = lane_id(context)
    claim_token = secrets.token_hex(16)
    value = {
        "schema_version": SCHEMA_VERSION,
        "change_id": change_id,
        "lane_id": identifier,
        "status": "claiming",
        "claim_token": claim_token,
        "scope": args.scope or "",
        "paths": [],
        "base_commit": context["head"],
        "completion_commit": None,
        "validation": [],
        "validation_passed": False,
        "evidence_complete": False,
        "contract_required": False,
        "contract_path": None,
        "evidence_paths": [str(target.relative_to(skill_root)).replace("\\", "/")],
        "integrated_by": None,
        "integration_status": "not_requested",
        "repository_mode": context["mode"],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    record_path = change_record_path(skill_root, change_id)
    atomic_create_json(record_path, value)
    created_target = False
    try:
        target.mkdir(parents=True)
        created_target = True
        copy_change_templates(skill_root, target, change_id)
        ensure_lane(skill_root, context, change_id)
        value["status"] = "planning"
        value["updated_at"] = utc_now()
        atomic_write_json(record_path, value)
        rebuild_change_index(skill_root)
    except Exception:
        if created_target and target.exists():
            remove_owned_tree(target, target.parent, "Failed Change evidence claim")
        current = read_json(record_path, {})
        if current.get("claim_token") == claim_token:
            record_path.unlink(missing_ok=True)
        try:
            lane_path = registry_root(skill_root) / "lanes" / f"{current_lane_id}.json"
            lane = read_json(lane_path, {})
            if lane.get("active_change_id") == change_id:
                ensure_lane(skill_root, context, None)
        except Exception:
            pass
        raise
    return {"status": "created", "change": value, "skill_path": str(target)}

def path_overlap(left: str, right: str) -> bool:
    left_value = left.strip("/")
    right_value = right.strip("/")
    return left_value == right_value or left_value.startswith(right_value + "/") or right_value.startswith(left_value + "/")

def normalize_claim(value: str) -> str:
    if not isinstance(value, str):
        raise HarnessError("Registry paths must be strings.")
    candidate = value.strip().replace("\\", "/")
    if not candidate or "\0" in candidate or candidate.startswith("/") or re.match(r"^[A-Za-z]:", candidate):
        raise HarnessError(f"Registry paths must be non-empty project-relative paths: {value}")
    parts = [part for part in candidate.split("/") if part not in {"", "."}]
    if ".." in parts:
        raise HarnessError(f"Registry paths must not traverse outside the project: {value}")
    return "/".join(parts)

def baseline_event_contracts(skill_root: Path, event: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in event.get("contracts", []):
        if isinstance(item, str):
            contract = load_contract_record(skill_root, item)
        elif isinstance(item, dict):
            change_id = canonical_id(str(item.get("change_id", "")), "Contract Change id")
            if item.get("change_id") != change_id:
                raise HarnessError("Baseline event contract contains a non-canonical Change id.")
            contract = item
        else:
            raise HarnessError("Baseline event contracts must be Change ids or contract objects.")
        if contract:
            result.append(contract)
    return result

def baseline_event_impacts(
    skill_root: Path,
    context: dict[str, Any],
    current: dict[str, Any],
    current_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    base = current.get("base_commit")
    if not base or context["mode"] != "multi_lane":
        return []
    impacts = []
    for path in sorted((registry_root(skill_root) / "baseline-events").glob("*.json")):
        event = read_json(path, {})
        if not isinstance(event, dict) or event.get("event") != "canonical-baseline-advanced":
            continue
        canonical = event.get("canonical_commit")
        if not canonical or canonical == base:
            continue
        if git(context["project_root"], "merge-base", "--is-ancestor", base, canonical, check=False).returncode != 0:
            continue
        reasons: set[str] = set()
        affected_contracts = []
        event_paths = [normalize_claim(item) for item in event.get("affected_paths", [])]
        path_reasons = {
            f"path:{left} <-> {right}"
            for left in current.get("paths", [])
            for right in event_paths
            if path_overlap(left, right)
        }
        reasons.update(path_reasons)
        for contract in baseline_event_contracts(skill_root, event):
            contract_reasons: set[str] = set()
            subject = contract.get("subject")
            changed_paths = [normalize_claim(item) for item in contract.get("affected_paths", [])]
            overlaps = sorted({
                f"{left} <-> {right}"
                for left in current.get("paths", [])
                for right in changed_paths
                if path_overlap(left, right)
            })
            if overlaps:
                contract_reasons.update(f"path:{item}" for item in overlaps)
            if current_contract:
                if subject and subject == current_contract.get("subject"):
                    contract_reasons.add(f"same_subject:{subject}")
                if subject and subject in current_contract.get("depends_on", []):
                    contract_reasons.add(f"depends_on_subject:{subject}")
                if contract.get("change_id") in current_contract.get("depends_on_changes", []):
                    contract_reasons.add(f"depends_on_change:{contract.get('change_id')}")
                if contract.get("owner_module") in current_contract.get("consumers", []):
                    contract_reasons.add(f"consumer_module:{contract.get('owner_module')}")
            if contract_reasons:
                affected_contracts.append(contract.get("change_id"))
                reasons.update(contract_reasons)
        if reasons:
            impacts.append({
                "event": path.name,
                "integration_id": event.get("integration_id"),
                "canonical_commit": canonical,
                "reasons": sorted(reasons),
                "contracts": sorted(set(item for item in affected_contracts if item)),
                "knowledge_refresh_needed": True,
            })
    return impacts

def knowledge_drift_impacts(
    skill_root: Path,
    context: dict[str, Any],
    current: dict[str, Any],
    current_contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    wiki = skill_root / "references" / "project_wiki"
    baseline = read_json(wiki / KNOWLEDGE_BASELINE_FILE, {})
    baseline_documents = baseline.get("documents", {}) if isinstance(baseline, dict) else {}
    items = discover_project_knowledge(skill_root, context)
    current_paths = [
        normalize_claim(item)
        for item in [
            *current.get("paths", []),
            *current_contract.get("affected_paths", []),
        ]
    ]
    owner_module = current_contract.get("owner_module") if current_contract else None
    selected_sources: dict[str, set[str]] = {}
    for item in items:
        item_id = str(item.get("id") or "")
        record = baseline_documents.get(item_id, {}) if isinstance(baseline_documents, dict) else {}
        fingerprints = record.get("source_fingerprints", {}) if isinstance(record, dict) else {}
        if not item_id or not isinstance(fingerprints, dict):
            continue
        module_related = bool(
            owner_module
            and slugify(str(owner_module)) in item.get("modules", [])
        )
        related_sources = {
            source for source in fingerprints
            if isinstance(source, str)
            and any(path_overlap(path, source) for path in current_paths)
        }
        if module_related:
            related_sources.update(
                source for source in fingerprints if isinstance(source, str)
            )
        if related_sources:
            selected_sources[item_id] = related_sources

    scan = knowledge_fingerprint_scan(skill_root, context, selected_sources)
    drift_by_item: dict[str, list[str]] = {}
    for finding in scan["findings"]:
        if finding["type"] not in {"changed", "missing"}:
            continue
        item_id = str(finding.get("item") or "")
        source = finding.get("source")
        if item_id and isinstance(source, str):
            drift_by_item.setdefault(item_id, []).append(source)
    impacts = []
    for item in items:
        drifted_sources = sorted(set(drift_by_item.get(str(item.get("id") or ""), [])))
        related_sources = sorted({
            source for source in drifted_sources
            if any(path_overlap(path, source) for path in current_paths)
        })
        module_related = bool(
            owner_module
            and slugify(str(owner_module)) in item.get("modules", [])
        )
        if drifted_sources and (related_sources or module_related):
            impacts.append({
                "knowledge_id": item.get("id"),
                "layer": item.get("layer"),
                "path": item.get("path"),
                "drifted_sources": sorted(drifted_sources),
                "related_sources": sorted(related_sources),
                "reason": "module_owner" if module_related and not related_sources else "path_overlap",
            })
    return impacts, {
        "candidate_items": len(selected_sources),
        "checked_sources": scan["unique_sources"],
    }

@guard_project_skill
def change_preflight(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    lane = ensure_lane(skill_root, context)
    requested_change_id = args.change_id or lane.get("active_change_id")
    change_id = canonical_id(requested_change_id, "Change id") if requested_change_id else None
    current = load_change_record(skill_root, change_id, required=bool(args.change_id)) if change_id else {}
    conflicts = []
    historical_overlaps = []
    for other in change_records(skill_root):
        if (
            other.get("change_id") == change_id
            or other.get("integrated_by")
            or other.get("status") not in {"planning", "active", "completed"}
        ):
            continue
        overlaps = sorted({
            f"{left} <-> {right}"
            for left in current.get("paths", [])
            for right in other.get("paths", [])
            if path_overlap(left, right)
        })
        if overlaps:
            finding = {"type": "path", "other_change_id": other.get("change_id"), "details": overlaps}
            (historical_overlaps if other.get("status") == "completed" else conflicts).append(finding)
    if context["mode"] == "multi_lane":
        current_contract = load_contract_record(skill_root, change_id) if change_id else {}
        for other in contract_records(skill_root):
            other_change = load_change_record(skill_root, other["change_id"])
            if (
                other.get("change_id") == change_id
                or other.get("status") in {"retired", "integrated"}
                or other_change.get("integrated_by")
                or other_change.get("status") not in {"planning", "active", "completed"}
            ):
                continue
            same_subject = current_contract and current_contract.get("subject") == other.get("subject")
            dependency = other.get("subject") in current_contract.get("depends_on", []) if current_contract else False
            reverse_dependency = current_contract.get("subject") in other.get("depends_on", []) if current_contract else False
            if same_subject or dependency or reverse_dependency:
                finding = {
                    "type": "contract", "other_change_id": other.get("change_id"),
                    "subject": other.get("subject"), "relationship": "same_subject" if same_subject else "dependency",
                }
                (historical_overlaps if other_change.get("status") == "completed" else conflicts).append(finding)
    baseline = read_json(registry_root(skill_root) / "baseline.json", {})
    relation = "not_applicable"
    if current and context["mode"] == "multi_lane":
        base = current.get("base_commit")
        canonical = baseline.get("canonical_commit")
        relation = git_baseline_relation(context["project_root"], base, canonical)
    current_contract = load_contract_record(skill_root, change_id) if change_id else {}
    baseline_impacts = baseline_event_impacts(skill_root, context, current, current_contract) if current else []
    drift_impacts, drift_scope = (
        knowledge_drift_impacts(skill_root, context, current, current_contract)
        if current else ([], {"candidate_items": 0, "checked_sources": 0})
    )
    refresh_needed = bool(baseline_impacts or drift_impacts)
    return {
        "project_id": context["project_id"], "mode": context["mode"], "lane": lane,
        "change": current or None, "conflicts": conflicts,
        "historical_overlaps": historical_overlaps,
        "baseline": baseline,
        "baseline_relation": relation,
        "baseline_advanced": relation == "canonical_advanced",
        "baseline_impacts": baseline_impacts,
        "knowledge": {
            "model": "periodic_index",
            "status": "refresh-needed" if refresh_needed else "current-for-change-scope",
            **drift_scope,
            "drift_impacts": drift_impacts,
            "fact_priority": [
                "registry contracts and baseline events",
                "shared current Change evidence",
                "repository code, manifests, configuration, tests, and accepted interfaces",
                "L1/L2/L3 periodic index",
            ],
        },
        "action": "replan" if conflicts or refresh_needed or relation in {"diverged", "unavailable"} else "continue",
    }

def validate_contract(contract: dict[str, Any], change_id: str) -> None:
    required = {"kind", "subject", "operation", "owner_module", "compatibility", "status"}
    missing = sorted(key for key in required if not contract.get(key))
    if missing:
        raise HarnessError(f"Contract is missing required fields: {', '.join(missing)}")
    if contract.get("change_id") not in {None, change_id}:
        raise HarnessError("Contract change_id does not match the published Change.")
    if contract.get("kind") not in {"api", "schema", "event", "config", "permission", "module_boundary"}:
        raise HarnessError("Contract kind must be api, schema, event, config, permission, or module_boundary.")
    for field in ("affected_paths", "consumers", "depends_on", "depends_on_changes"):
        if field in contract and not isinstance(contract[field], list):
            raise HarnessError(f"Contract field {field} must be a list.")
    contract["affected_paths"] = sorted({normalize_claim(item) for item in contract.get("affected_paths", [])})
    contract["depends_on_changes"] = sorted({
        canonical_id(item, "Contract dependency Change id") for item in contract.get("depends_on_changes", [])
    })

@guard_project_skill
def change_publish(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    change_id = canonical_id(args.change_id, "Change id")
    path = change_record_path(skill_root, change_id)
    value = load_change_record(skill_root, change_id, required=True)
    require_change_owner(context, value)
    if value.get("status") in TERMINAL_CHANGE_STATUSES:
        raise HarnessError(f"Terminal Change cannot be published: {value.get('status')}")
    if args.scope is not None:
        value["scope"] = args.scope
    if args.paths is not None:
        value["paths"] = sorted({normalize_claim(item) for item in args.paths})
    if args.status is not None:
        value["status"] = args.status
    if args.validation is not None:
        value["validation"] = args.validation
    if args.contract:
        contract = read_json(Path(args.contract))
        if not isinstance(contract, dict):
            raise HarnessError("Contract file must contain one JSON object.")
        validate_contract(contract, change_id)
        contract["schema_version"] = SCHEMA_VERSION
        contract["change_id"] = change_id
        contract["updated_at"] = utc_now()
        target = contract_record_path(skill_root, change_id)
        atomic_write_json(target, contract)
        value["contract_required"] = True
        value["contract_path"] = target.relative_to(skill_root).as_posix()
    value["updated_at"] = utc_now()
    atomic_write_json(path, value)
    ensure_lane(skill_root, context, change_id if value["status"] in {"planning", "active"} else None)
    rebuild_change_index(skill_root)
    return {"status": "published", "change": value}

def eligible_changes(skill_root: Path) -> list[dict[str, Any]]:
    result = []
    for item in change_records(skill_root):
        if (
            item.get("status") == "completed"
            and item.get("validation")
            and item.get("validation_passed") is True
            and item.get("evidence_complete") is True
        ):
            result.append(item)
    return sorted(result, key=lambda item: (item.get("updated_at", ""), item.get("change_id", "")))

def evolve_check_locked(skill_root: Path) -> dict[str, Any]:
    state_path = skill_root / "state" / "evolution" / "state.json"
    state = read_json(state_path, {})
    evaluated = set(state.get("evaluated_change_ids", []))
    unevaluated_ids = [item["change_id"] for item in eligible_changes(skill_root) if item["change_id"] not in evaluated]
    owner = skill_root / "state" / "registry" / "locks" / "evolution-owner"
    frozen = bool(state.get("pending") and owner.exists())
    threshold = int(state.get("threshold", EVOLUTION_THRESHOLD))
    pending_ids = list(state.get("pending_change_ids", [])) if frozen else unevaluated_ids[:threshold]
    queued_ids = [change_id for change_id in unevaluated_ids if change_id not in set(pending_ids)]
    due = bool(frozen or len(unevaluated_ids) >= threshold)
    if due:
        state["pending"] = True
        state["pending_change_ids"] = pending_ids
        atomic_write_json(
            skill_root / "state" / "evolution" / "pending.json",
            {
                "schema_version": SCHEMA_VERSION,
                "threshold": threshold,
                "change_ids": pending_ids,
                "queued_change_ids": queued_ids,
                "required_flow": [
                    "Ask E1",
                    "Claim evolution and shared writer ownership",
                    "Create proposal and staged candidate",
                    "Run independent judge and required validation",
                    "Mark keep, rejected, or noop without E2",
                ],
                "updated_at": utc_now(),
            },
        )
    else:
        state["pending"] = False
        state["pending_change_ids"] = []
        pending = skill_root / "state" / "evolution" / "pending.json"
        if pending.exists():
            pending.unlink()
    atomic_write_json(state_path, state)
    return {
        "due": due,
        "eligible_unevaluated": pending_ids,
        "queued_for_next_window": queued_ids,
        "threshold": threshold,
        "pending": state.get("pending", False),
        "frozen": frozen,
    }

def evolve_check_internal(skill_root: Path) -> dict[str, Any]:
    with short_registry_lock(skill_root, "evolution-state"):
        return evolve_check_locked(skill_root)

def change_evidence_complete(path: Path) -> tuple[bool, list[str]]:
    return validate_change_evidence(path)

def validate_completion_commit(context: dict[str, Any], value: dict[str, Any], commit: str) -> str:
    root: Path = context["project_root"]
    resolved = git_value(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
    if not resolved:
        raise HarnessError(f"Completion commit does not exist: {commit}")
    base = value.get("base_commit")
    if not base:
        raise HarnessError("Completion commit cannot be recorded because the Change has no Git base commit.")
    if git(root, "merge-base", "--is-ancestor", base, resolved, check=False).returncode != 0:
        raise HarnessError("Completion commit is not descended from the Change base commit.")
    head = git_value(root, "rev-parse", "HEAD")
    if not head or git(root, "merge-base", "--is-ancestor", resolved, head, check=False).returncode != 0:
        raise HarnessError("Completion commit is not reachable from the current Lane HEAD.")
    commits = [line for line in git(root, "rev-list", "--reverse", f"{base}..{resolved}").stdout.splitlines() if line]
    if not commits:
        raise HarnessError("Completion commit produces an empty Change range.")
    for candidate in commits:
        if len(git(root, "rev-list", "--parents", "-n", "1", candidate).stdout.split()) > 2:
            raise HarnessError(f"Completion range contains merge commit {candidate}; use a linear Change range.")
    return resolved

@guard_project_skill
def change_close(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    change_id = canonical_id(args.change_id, "Change id")
    path = change_record_path(skill_root, change_id)
    value = load_change_record(skill_root, change_id, required=True)
    require_change_owner(context, value)
    if value.get("status") in TERMINAL_CHANGE_STATUSES:
        if value.get("status") == args.status:
            return {"status": "already_closed", "change": value, "evolution": evolve_check_internal(skill_root)}
        raise HarnessError(f"Change is already terminal: {value.get('status')}")
    if args.validation:
        value["validation"] = args.validation
    if args.validation_passed:
        value["validation_passed"] = True
    value["updated_at"] = utc_now()
    source = active_change_dir(skill_root, change_id)
    destination = archive_change_dir(skill_root, change_id)
    evidence = source if source.exists() else destination
    if not evidence.exists():
        raise HarnessError("Change evidence exists in neither active nor archive state.")
    require_physical_change_evidence(evidence, "Change close evidence")
    complete, missing = change_evidence_complete(evidence)
    if args.status == "completed":
        if missing:
            raise HarnessError(f"Completed Change evidence is incomplete: {'; '.join(missing)}")
        if not (args.validation or value.get("validation")) or not (args.validation_passed or value.get("validation_passed")):
            raise HarnessError("Completed Change requires passing validation evidence.")
        if args.completion_commit:
            if context["mode"] != "multi_lane":
                raise HarnessError("Completion commit metadata is only available for Git-backed Changes.")
            value["completion_commit"] = validate_completion_commit(context, value, args.completion_commit)
    knowledge = rebuild_project_wiki_catalog(skill_root, context)
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or is_link_like(destination):
            raise HarnessError(f"Archive Change directory already exists: {destination}")
        require_physical_change_evidence(source, "Active Change evidence")
        shutil.move(str(source), str(destination))
    value["evidence_paths"] = [str(destination.relative_to(skill_root)).replace("\\", "/")]
    value["status"] = args.status
    value["evidence_complete"] = complete
    value["updated_at"] = utc_now()
    atomic_write_json(path, value)
    ensure_lane(skill_root, context, None)
    rebuild_change_index(skill_root)
    evolution = evolve_check_internal(skill_root)
    return {
        "status": "closed",
        "change": value,
        "integration_boundary": "recorded" if value.get("completion_commit") else "not_recorded",
        "knowledge": {"items": len(knowledge["items"]), "refreshed": knowledge["refreshed"]},
        "evolution": evolution,
    }

@guard_project_skill
def change_park(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    change_id = canonical_id(args.change_id, "Change id")
    value = load_change_record(skill_root, change_id, required=True)
    require_change_owner(context, value)
    if value.get("status") not in {"planning", "active"}:
        raise HarnessError(f"Only a planning or active Change may be parked: {value.get('status')}")
    source = active_change_dir(skill_root, change_id)
    destination = parking_change_dir(skill_root, change_id)
    require_physical_change_evidence(source, "Active Change evidence")
    if destination.exists() or is_link_like(destination):
        raise HarnessError(f"Parking Change directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    value["status"] = "parking"
    value["evidence_paths"] = [destination.relative_to(skill_root).as_posix()]
    value["updated_at"] = utc_now()
    atomic_write_json(change_record_path(skill_root, change_id), value)
    ensure_lane(skill_root, context, None)
    rebuild_change_index(skill_root)
    return {"status": "parked", "change": value}

@guard_project_skill
def change_resume(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    change_id = canonical_id(args.change_id, "Change id")
    value = load_change_record(skill_root, change_id, required=True)
    if value.get("status") != "parking":
        raise HarnessError(f"Only a parked Change may be resumed: {value.get('status')}")
    current_lane_id = lane_id(context)
    active_on_lane = [
        item for item in change_records(skill_root)
        if item.get("lane_id") == current_lane_id
        and item.get("status") in {"planning", "active"}
    ]
    if active_on_lane:
        raise HarnessError("This Lane already has an active Change.")
    if context["mode"] == "multi_lane":
        if not value.get("base_commit"):
            value["base_commit"] = context["head"]
    source = parking_change_dir(skill_root, change_id)
    destination = active_change_dir(skill_root, change_id)
    require_physical_change_evidence(source, "Parked Change evidence")
    if destination.exists() or is_link_like(destination):
        raise HarnessError(f"Active Change directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    value["status"] = "active"
    value["lane_id"] = current_lane_id
    value["evidence_paths"] = [destination.relative_to(skill_root).as_posix()]
    value["updated_at"] = utc_now()
    atomic_write_json(change_record_path(skill_root, change_id), value)
    ensure_lane(skill_root, context, change_id)
    rebuild_change_index(skill_root)
    return {"status": "resumed", "change": value}

@guard_project_skill
def change_reindex(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    index = rebuild_change_index(skill_root)
    knowledge = rebuild_project_wiki_catalog(skill_root, context)
    return {
        "status": "reindexed",
        "count": len(index["changes"]),
        "index": index,
        "knowledge": {"items": len(knowledge["items"]), "refreshed": knowledge["refreshed"]},
    }

@guard_project_skill
def change_search(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    index = read_json(changes_root(skill_root) / "INDEX.json", {})
    query = (args.query or "").strip().lower()
    statuses = set(args.status or [])
    matches = []
    for item in index.get("changes", []):
        if statuses and item.get("status") not in statuses:
            continue
        searchable = " ".join([
            str(item.get("change_id", "")), str(item.get("scope", "")),
            " ".join(item.get("paths", [])), " ".join(item.get("tags", [])),
            str(item.get("summary_excerpt", "")),
        ]).lower()
        if query and query not in searchable:
            continue
        matches.append(item)
    return {"query": args.query, "count": len(matches), "changes": matches}

@guard_project_skill
def change_context(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    change_id = canonical_id(args.change_id, "Change id")
    value = load_change_record(skill_root, change_id, required=True)
    evidence_state, evidence_path = locate_change_evidence(skill_root, change_id)
    if not evidence_path:
        raise HarnessError("Change evidence is missing.")
    requested = (
        sorted(REQUIRED_CHANGE_FILES)
        if args.full
        else ["summary.md"]
    )
    documents = {}
    for relative in requested:
        path = evidence_path / relative
        if path.is_file():
            documents[relative] = path.read_text(encoding="utf-8", errors="replace")
    return {
        "change": value,
        "evidence_state": evidence_state,
        "evidence_path": evidence_path.relative_to(skill_root).as_posix(),
        "documents": documents,
    }

@guard_project_skill
def change_status(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    items = change_records(skill_root)
    if args.change_id:
        change_id = canonical_id(args.change_id, "Change id")
        items = [item for item in items if item.get("change_id") == change_id]
    return {"changes": items}
