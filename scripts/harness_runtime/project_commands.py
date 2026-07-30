"""Project init, audit, portable migration, and doctor orchestration."""

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

from .analysis import load_analysis_bundle
from .changes import contract_record_path, ecl_integrity_findings
from .core import HarnessError, MANIFEST_SCHEMA_VERSION, SCHEMA_VERSION, atomic_write_json, atomic_write_text, git_value, is_within, read_json, run, safe_relative, stable_hash, utc_now
from .evolution import copy_non_state_skill
from .integration import load_integration_record
from .knowledge import context_source_fingerprints, knowledge_check_internal
from .links import connector_route, copy_runtime, copy_scaffold, ensure_all_project_routes, ensure_runtime_links, generated_command_routes, remove_directory_link, restore_route_snapshots, same_target, worktree_route_findings
from .project import assign_project_identity, ensure_state, initial_manifest, project_context, require_skill, skill_root_for, worktree_roots
from .registry import records, registry_root
from .rendering import install_analysis_bundle
from .transactions import acquire_writer, apply_content_transaction, capture_file_snapshots, commit_content_transaction, content_transaction_store, guard_project_skill, guard_project_skill_read_only, recover_content_transactions, release_writer, restore_file_snapshots, rollback_content_transaction, writer_lock_path

def project_init(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    if context.get("project_id"):
        raise HarnessError("Project routes already declare a Harness identity. Run project migrate or doctor instead.")
    assign_project_identity(context)
    skill_root = skill_root_for(context, args)
    if (skill_root / "state" / "manifest.json").exists():
        raise HarnessError(f"Project Harness Skill already exists: {skill_root}")
    profile, audit, delta, architecture, bundle = load_analysis_bundle(args, context)
    replacements = {
        "SKILL_NAME": context["skill_name"],
        "PROJECT_NAME": context["project_name"],
        "PROJECT_ID": context["project_id"],
        "MODE": context["mode"],
        **generated_command_routes(),
    }
    connector_name, connector_command = connector_route()
    replacements["CONNECTOR_COMMAND"] = connector_command
    created_links: list[Path] = []
    route_snapshots: dict[Path, bytes | None] = {}
    skill_root.mkdir(parents=True, exist_ok=False)
    try:
        copy_scaffold(skill_root, replacements)
        launchers = copy_runtime(skill_root)
        ensure_state(skill_root, context, getattr(args, "canonical_branch", None))
        installed = install_analysis_bundle(
            skill_root,
            context,
            profile,
            audit,
            delta,
            architecture,
            bundle,
            bool(getattr(args, "allow_executable_artifacts", False)),
        )
        links, new_links = ensure_runtime_links(context, args, skill_root)
        created_links.extend(new_links)
        manifest = initial_manifest(context, links, launchers)
        manifest["analysis_status"] = profile.get("analysis_status")
        atomic_write_json(skill_root / "state" / "manifest.json", manifest)
        routes, route_snapshots = ensure_all_project_routes(context, skill_root)
        return {
            "status": "initialized" if profile.get("analysis_status") == "complete" else "bootstrapped",
            "semantic_complete": profile.get("analysis_status") == "complete",
            "skill_root": str(skill_root), "project_id": context["project_id"],
            "mode": context["mode"], "runtime_links": links, "routes": routes, **installed,
        }
    except Exception:
        restore_route_snapshots(route_snapshots)
        for link in reversed(created_links):
            remove_directory_link(link, skill_root)
        if skill_root.exists():
            shutil.rmtree(skill_root, ignore_errors=True)
        raise

@guard_project_skill_read_only
def project_audit(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    had_identity = bool(context.get("project_id"))
    semantic = None
    if getattr(args, "analysis_bundle", None):
        if not context.get("project_id"):
            assign_project_identity(context)
        profile, audit, delta, architecture, _ = load_analysis_bundle(args, context)
        semantic = {
            "analysis_status": profile.get("analysis_status"),
            "purpose": profile.get("purpose"),
            "architecture": architecture,
            "modules": [item.get("id") for item in profile.get("modules", [])],
            "bridges": [item.get("id") for item in profile.get("bridges", [])],
            "commands": len(profile.get("commands", [])),
            "gaps": audit.get("gaps", []),
            "decisions": delta.get("decisions", []),
        }
    if not had_identity:
        return {
            "project_id": None, "mode": context["mode"], "skill_root": None,
            "initialized": False, "findings": ["project_skill_missing"], "doctor": None,
            "knowledge": None, "ecl": {"healthy": False, "findings": []},
            "rules": None, "semantic": semantic,
        }
    root = skill_root_for(context, args)
    initialized = (root / "state" / "manifest.json").exists()
    findings = []
    if not initialized:
        findings.append("project_skill_missing")
    doctor = project_doctor_internal(args) if initialized else None
    knowledge = knowledge_check_internal(root, context) if initialized else None
    ecl_findings = ecl_integrity_findings(root) if initialized else []
    rules = rule_views_check(root) if initialized else None
    if doctor and not doctor["healthy"]:
        findings.append("project_skill_drift")
    if knowledge and not knowledge["healthy"]:
        findings.append("project_knowledge_drift")
    if ecl_findings:
        findings.append("project_change_evidence_drift")
    if rules and not rules["healthy"]:
        findings.append("project_rule_view_drift")
    return {
        "project_id": context["project_id"], "mode": context["mode"], "skill_root": str(root),
        "initialized": initialized, "findings": findings, "doctor": doctor,
        "knowledge": knowledge,
        "ecl": {"healthy": not ecl_findings, "findings": ecl_findings},
        "rules": rules,
        "semantic": semantic,
    }

def portable_manifest(manifest: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project_id": context["project_id"],
        "project_name": manifest.get("project_name") or context["project_name"],
        "skill_name": context["skill_name"],
        "skill_revision": int(manifest.get("skill_revision", 1)),
        "analysis_status": manifest.get("analysis_status", "bootstrap_only"),
        "launchers": manifest.get("launchers", []),
        "created_at": manifest.get("created_at") or now,
        "updated_at": now,
    }


def portable_lane_id(project_id: str, branch: str | None) -> str:
    return "lane-single" if not branch else f"lane-{stable_hash(f'{project_id}:{branch}', 10)}"


def normalize_portable_state(root: Path, context: dict[str, Any]) -> None:
    manifest_path = root / "state" / "manifest.json"
    manifest = read_json(manifest_path, {})
    atomic_write_json(manifest_path, portable_manifest(manifest, context))

    baseline_path = registry_root(root) / "baseline.json"
    baseline = read_json(baseline_path, {})
    baseline.pop("canonical_root", None)
    if context.get("mode") == "multi_lane" and not baseline.get("canonical_branch"):
        baseline["canonical_branch"] = context.get("branch")
        baseline["canonical_commit"] = context.get("head")
        baseline["updated_at"] = utc_now()
    atomic_write_json(baseline_path, baseline)

    lane_map: dict[str, str] = {}
    lanes_dir = registry_root(root) / "lanes"
    for lane_path in sorted(lanes_dir.glob("*.json")):
        lane = read_json(lane_path, {})
        branch = lane.get("branch") or (context.get("branch") if lane.get("lane_id") == "lane-single" else None)
        identifier = portable_lane_id(context["project_id"], branch)
        lane_map[str(lane.get("lane_id"))] = identifier
        lane.pop("worktree", None)
        lane["lane_id"] = identifier
        lane["branch"] = branch
        target = lanes_dir / f"{identifier}.json"
        atomic_write_json(target, lane)
        if target != lane_path:
            lane_path.unlink()

    for path in sorted((registry_root(root) / "changes").glob("*.json")):
        change = read_json(path, {})
        changed = False
        if change.get("status") not in {"completed", "blocked", "abandoned"}:
            change["lane_id"] = lane_map.get(str(change.get("lane_id")), change.get("lane_id"))
            if context.get("mode") == "multi_lane" and not change.get("base_commit"):
                change["base_commit"] = baseline.get("canonical_commit") or context.get("head")
            changed = True
        if change.get("contract_path"):
            contract_path = contract_record_path(root, str(change.get("change_id", "")))
            if not contract_path.is_file():
                raise HarnessError(
                    f"Change {change.get('change_id')!r} names a contract but its Registry contract record is missing."
                )
            change["contract_path"] = contract_path.relative_to(root).as_posix()
            changed = True
        if changed:
            atomic_write_json(path, change)

    for path in sorted((registry_root(root) / "integrations").glob("*.json")):
        record = read_json(path, {})
        integration_id = record.get("integration_id") or path.stem
        record["worktree"] = f"state/integrations/{integration_id}"
        atomic_write_json(path, record)

@guard_project_skill
def project_migrate(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    if not context.get("project_id"):
        init_result = project_init(args)
        return {
            "status": "migration_applied",
            "init": init_result,
            "applied": {
                "via": "project_init",
                "knowledge": init_result.get("knowledge"),
                "artifacts": init_result.get("artifacts"),
                "rules": init_result.get("rules"),
            },
            "routes": init_result.get("routes", {}),
        }
    root = skill_root_for(context, args)
    profile = audit = delta = architecture = bundle = None
    if getattr(args, "analysis_bundle", None):
        profile, audit, delta, architecture, bundle = load_analysis_bundle(args, context)
    if not (root / "state" / "manifest.json").exists():
        raise HarnessError(
            "Project routes identify a Harness that is not present on this machine. Place the matching project Harness at the marked Skill path before migrating."
        )
    else:
        init_result = None
    existing_manifest = read_json(root / "state" / "manifest.json", {})
    if existing_manifest.get("project_id") != context["project_id"]:
        raise HarnessError("Project id does not match the local Harness manifest.")
    if root.name != context["skill_name"]:
        raise HarnessError("Project Harness directory name does not match project identity.")
    existing_schema = existing_manifest.get("schema_version")
    if existing_schema not in {SCHEMA_VERSION, MANIFEST_SCHEMA_VERSION}:
        raise HarnessError(f"Unsupported project Harness manifest schema: {existing_schema!r}")
    portable_upgrade = existing_schema != MANIFEST_SCHEMA_VERSION
    state_rebind = any(
        lane.get("lane_id") != portable_lane_id(
            context["project_id"],
            lane.get("branch") or (context.get("branch") if lane.get("lane_id") == "lane-single" else None),
        )
        or "worktree" in lane
        for lane in records(registry_root(root) / "lanes")
    )
    if portable_upgrade and existing_manifest.get("analysis_status") == "complete":
        if profile is None or profile.get("analysis_status") != "complete":
            raise HarnessError(
                "semantic_refresh_required: this complete project Harness must be migrated with a new complete self-contained analysis bundle."
            )
    if not portable_upgrade:
        root = require_skill(context, args)
    routes: dict[str, dict[str, str]] = {}
    route_snapshots: dict[Path, bytes | None] = {}
    created_links: list[Path] = []
    applied = None
    if init_result and bundle is not None and init_result.get("status") in {"initialized", "bootstrapped"}:
        applied = {
            "via": "project_init",
            "knowledge": init_result.get("knowledge"),
            "artifacts": init_result.get("artifacts"),
            "rules": init_result.get("rules"),
        }
    if profile is not None or portable_upgrade or state_rebind:
        acquire_writer(root, "migration", context["project_id"])
        transaction: dict[str, Any] | None = None
        manifest_path = root / "state" / "manifest.json"
        snapshot_paths = [manifest_path, *sorted(registry_root(root).rglob("*.json"))]
        for lane in records(registry_root(root) / "lanes"):
            branch = lane.get("branch") or (context.get("branch") if lane.get("lane_id") == "lane-single" else None)
            snapshot_paths.append(
                registry_root(root) / "lanes" / f"{portable_lane_id(context['project_id'], branch)}.json"
            )
        state_snapshots = capture_file_snapshots(dict.fromkeys(snapshot_paths))
        candidate = root / "state" / "migration" / "staging" / context["project_id"]
        try:
            recover_content_transactions(root, "migration", context["project_id"])
            if candidate.exists():
                shutil.rmtree(candidate)
            candidate.parent.mkdir(parents=True, exist_ok=True)
            copy_non_state_skill(root, candidate)
            (candidate / "state").mkdir(parents=True, exist_ok=True)
            atomic_write_json(
                candidate / "state" / "manifest.json",
                portable_manifest(read_json(manifest_path, {}), context),
            )
            launchers = copy_runtime(candidate)
            if profile is not None and audit is not None and delta is not None and architecture is not None:
                applied = install_analysis_bundle(
                    candidate,
                    context,
                    profile,
                    audit,
                    delta,
                    architecture,
                    bundle,
                    bool(getattr(args, "allow_executable_artifacts", False)),
                )
            else:
                applied = {"portable_state_upgrade": portable_upgrade, "lane_rebound": state_rebind}
                if state_rebind:
                    index_path = candidate / "references" / "project_wiki" / "index.json"
                    index = read_json(index_path, {})
                    for item in index.get("items", []):
                        sources = item.get("sources", [])
                        if isinstance(sources, list):
                            item["source_fingerprints"] = context_source_fingerprints(context, sources)
                    atomic_write_json(index_path, index)
            candidate_check = knowledge_check_internal(candidate, context)
            if not candidate_check["healthy"]:
                raise HarnessError(f"Migration candidate knowledge validation failed: {candidate_check['findings']}")
            transaction = apply_content_transaction(
                root,
                candidate,
                "migration",
                context["project_id"],
                state_snapshot_paths=state_snapshots,
            )
            links, new_links = ensure_runtime_links(context, args, root)
            created_links.extend(new_links)
            routes, route_snapshots = ensure_all_project_routes(context, root)
            normalize_portable_state(root, context)
            manifest = read_json(manifest_path, {})
            if profile is not None:
                manifest["analysis_status"] = profile.get("analysis_status")
            manifest["skill_revision"] = int(manifest.get("skill_revision", 1)) + 1
            manifest["launchers"] = launchers
            manifest["updated_at"] = utc_now()
            atomic_write_json(manifest_path, manifest)
            commit_content_transaction(transaction)
            transaction = None
        except Exception:
            restore_route_snapshots(route_snapshots)
            for link in reversed(created_links):
                remove_directory_link(link, root)
            if transaction is not None:
                rollback_content_transaction(transaction)
            restore_file_snapshots(state_snapshots)
            if candidate.exists():
                shutil.rmtree(candidate, ignore_errors=True)
            raise
        finally:
            release_writer(root, "migration", context["project_id"])
    else:
        links, _ = ensure_runtime_links(context, args, root)
        routes, _ = ensure_all_project_routes(context, root)
    return {
        "status": "migration_applied" if applied else "migration_checked",
        "init": init_result, "applied": applied,
        "routes": routes,
    }

def rule_views_check(skill_root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    source = skill_root / "references" / "rules" / "red_lines.yaml"
    script = skill_root / "scripts" / "generate_rule_docs.py"
    if not source.is_file() or not script.is_file():
        return {"healthy": False, "findings": [{"type": "missing_rule_source_or_generator"}]}
    with tempfile.TemporaryDirectory(prefix="harness-rule-check-") as temporary:
        output = Path(temporary)
        result = run(
            [sys.executable, str(script), "--source", str(source), "--output-root", str(output)],
            check=False,
        )
        if result.returncode != 0:
            return {"healthy": False, "findings": [{"type": "invalid_rule_source", "detail": result.stdout}]}
        expected = {
            path.relative_to(output).as_posix(): path.read_text(encoding="utf-8")
            for path in output.rglob("*.md")
        }
        actual_root = skill_root / "references" / "rules"
        actual = {
            path.relative_to(actual_root).as_posix(): path.read_text(encoding="utf-8")
            for path in actual_root.rglob("*.md")
        }
        for relative in sorted(set(expected) | set(actual)):
            if relative not in actual:
                findings.append({"type": "missing_derived_rule_view", "path": relative})
            elif relative not in expected:
                findings.append({"type": "unexpected_derived_rule_view", "path": relative})
            elif actual[relative] != expected[relative]:
                findings.append({"type": "divergent_derived_rule_view", "path": relative})
    return {"healthy": not findings, "findings": findings}

def project_doctor_internal(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    root = require_skill(context, args)
    manifest = read_json(root / "state" / "manifest.json", {})
    findings = []
    repaired_routes = None
    if getattr(args, "repair_links", False):
        ensure_runtime_links(context, args, root)
        repaired_routes, _ = ensure_all_project_routes(context, root)
        manifest["updated_at"] = utc_now()
        atomic_write_json(root / "state" / "manifest.json", manifest)
    launchers = manifest.get("launchers", [])
    if not isinstance(launchers, list):
        findings.append({"type": "invalid_runtime_inventory"})
        launchers = []
    for value in launchers:
        if not isinstance(value, str):
            findings.append({"type": "invalid_runtime_inventory_entry", "path": value})
            continue
        try:
            relative = safe_relative(value, "Runtime inventory path")
        except HarnessError as exc:
            findings.append({"type": "invalid_runtime_inventory_entry", "path": value, "detail": str(exc)})
            continue
        runtime_path = root / "scripts" / relative
        if not is_within(runtime_path.resolve(), root / "scripts"):
            findings.append({"type": "runtime_inventory_escape", "path": value})
        elif not runtime_path.is_file():
            findings.append({"type": "missing_runtime_file", "path": value})
    findings.extend(worktree_route_findings(context))
    live_branches = {
        git_value(worktree, "branch", "--show-current")
        for worktree in worktree_roots(context)
    }
    for lane in records(registry_root(root) / "lanes"):
        if lane.get("status") != "retired" and lane.get("branch") not in live_branches:
            findings.append({"type": "stale_lane", "lane_id": lane.get("lane_id"), "branch": lane.get("branch")})
        try:
            updated = datetime.fromisoformat(str(lane.get("updated_at", "")).replace("Z", "+00:00"))
            stale_after_hours = int(getattr(args, "stale_after_hours", 168))
            if lane.get("status") == "active" and updated < datetime.now(timezone.utc) - timedelta(hours=stale_after_hours):
                findings.append({"type": "stale_lane_timestamp", "lane_id": lane.get("lane_id"), "updated_at": lane.get("updated_at")})
        except ValueError:
            findings.append({"type": "invalid_lane_timestamp", "lane_id": lane.get("lane_id")})
    baseline = read_json(registry_root(root) / "baseline.json", {})
    if context.get("branch") == baseline.get("canonical_branch") and context.get("head") != baseline.get("canonical_commit"):
        findings.append({
            "type": "canonical_baseline_drift",
            "recorded": baseline.get("canonical_commit"), "current": context.get("head"),
        })
    owner = registry_root(root) / "locks" / "evolution-owner"
    evolution = read_json(root / "state" / "evolution" / "state.json", {})
    if owner.exists() and not evolution.get("pending"):
        findings.append({"type": "orphan_evolution_owner", "path": str(owner)})
    writer = read_json(writer_lock_path(root) / "owner.json", {})
    if writer:
        try:
            claimed_at = datetime.fromisoformat(str(writer.get("claimed_at", "")).replace("Z", "+00:00"))
            stale_after_hours = int(getattr(args, "stale_after_hours", 168))
            if claimed_at < datetime.now(timezone.utc) - timedelta(hours=stale_after_hours):
                findings.append({"type": "stale_shared_writer", "owner": writer})
        except ValueError:
            findings.append({"type": "invalid_shared_writer_timestamp", "owner": writer})
        if writer.get("kind") == "evolution" and not owner.exists():
            findings.append({"type": "orphan_shared_writer", "owner": writer})
        if writer.get("kind") == "integration":
            try:
                record = load_integration_record(root, writer.get("owner_id", ""), required=False)
            except HarnessError as exc:
                record = {}
                findings.append({"type": "invalid_integration_writer", "owner": writer, "detail": str(exc)})
            phase = record.get("landing_phase", "not_started")
            if record.get("status") in {None, "integrated", "aborted"}:
                findings.append({"type": "orphan_shared_writer", "owner": writer})
            elif record.get("status") == "ready_for_review" or phase in {
                "pre_merge", "canonical_landed", "registry_committed", "cleanup_complete",
            }:
                findings.append({
                    "type": "integration_recovery_required",
                    "integration_id": record.get("integration_id"),
                    "status": record.get("status"),
                    "landing_phase": phase,
                })
    transaction_store = content_transaction_store(root)
    if transaction_store.exists():
        for transaction_root in sorted(transaction_store.iterdir()):
            if transaction_root.is_dir():
                journal = read_json(transaction_root / "journal.json", {})
                findings.append({
                    "type": "incomplete_content_transaction",
                    "path": str(transaction_root),
                    "operation": journal.get("operation"),
                    "phase": journal.get("phase"),
                })
    return {
        "healthy": not findings,
        "findings": findings,
        "runtime_links": [],
        "repaired_routes": repaired_routes,
    }

@guard_project_skill
def project_doctor(args: argparse.Namespace) -> dict[str, Any]:
    return project_doctor_internal(args)
