"""Project init, audit, migrate, doctor, and single-Lane upgrade orchestration."""

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
from .changes import ecl_integrity_findings
from .core import HarnessError, SCHEMA_VERSION, TEXT_SUFFIXES, atomic_write_json, atomic_write_text, canonical_id, file_fingerprint, is_link_like, is_within, normalize_lexical_path, normalize_path, read_json, reject_tree_links, run, safe_relative, utc_now
from .evolution import copy_non_state_skill
from .integration import load_integration_record
from .knowledge import knowledge_check_internal
from .links import connector_route, copy_runtime, copy_scaffold, ensure_all_project_routes, ensure_runtime_links, generated_command_routes, remove_directory_link, restore_route_snapshots, same_target, worktree_route_findings
from .project import canonical_branch_and_commit, ensure_state, initial_manifest, local_root, primary_worktree_root, project_context, require_skill, skill_root_for
from .registry import records, registry_root
from .rendering import install_analysis_bundle
from .transactions import acquire_writer, apply_content_transaction, capture_file_snapshots, commit_content_transaction, content_transaction_store, guard_project_skill, guard_project_skill_read_only, recover_content_transactions, release_writer, restore_file_snapshots, rollback_content_transaction, writer_lock_path

def project_init(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
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
    semantic = None
    if getattr(args, "analysis_bundle", None):
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
    return {
        "project_id": context["project_id"], "mode": context["mode"], "skill_root": str(root),
        "initialized": initialized, "findings": findings, "doctor": doctor,
        "knowledge": knowledge,
        "ecl": {"healthy": not ecl_findings, "findings": ecl_findings},
        "rules": rules,
        "semantic": semantic,
    }

def validate_single_lane_predecessor(
    candidate: Path,
    manifest: dict[str, Any],
    project_path: str,
) -> tuple[str, list[dict[str, Any]]]:
    if is_link_like(candidate):
        raise HarnessError(f"Single-Lane predecessor must be a physical directory: {candidate}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError("Single-Lane predecessor manifest schema is invalid.")
    raw_id = manifest.get("project_id")
    old_id = canonical_id(raw_id, "Single-Lane predecessor project id")
    if raw_id != old_id or candidate.name != f"{old_id}-harness":
        raise HarnessError("Single-Lane predecessor project id does not match its directory.")
    if manifest.get("mode") != "single_lane":
        raise HarnessError("Single-Lane predecessor manifest mode is invalid.")
    if manifest.get("git_common_dir") not in (None, ""):
        raise HarnessError("Single-Lane predecessor unexpectedly records a Git common dir.")
    if normalize_path(Path(manifest.get("project_root", "."))) != project_path:
        raise HarnessError("Single-Lane predecessor project root does not match this project.")
    runtime_links = manifest.get("runtime_links")
    if not isinstance(runtime_links, list):
        raise HarnessError("Single-Lane predecessor runtime links are invalid.")
    allowed_paths = {
        "codex": normalize_lexical_path(
            Path(manifest["project_root"]) / ".agents" / "skills" / candidate.name,
        ),
        "claude": normalize_lexical_path(
            Path(manifest["project_root"]) / ".claude" / "skills" / candidate.name,
        ),
    }
    seen_runtimes: set[str] = set()
    for item in runtime_links:
        if not isinstance(item, dict) or not item.get("path"):
            raise HarnessError("Single-Lane predecessor runtime link record is invalid.")
        runtime = item.get("runtime")
        if runtime not in allowed_paths or runtime in seen_runtimes:
            raise HarnessError("Single-Lane predecessor runtime link owner is invalid.")
        if normalize_lexical_path(Path(item["path"])) != allowed_paths[runtime]:
            raise HarnessError("Single-Lane predecessor runtime link is outside project ownership.")
        seen_runtimes.add(runtime)
    if seen_runtimes != set(allowed_paths):
        raise HarnessError("Single-Lane predecessor runtime links are incomplete.")
    return old_id, runtime_links

def find_single_lane_predecessor(context: dict[str, Any], args: argparse.Namespace) -> Path | None:
    if context["mode"] != "multi_lane":
        return None
    root = local_root(context, args)
    if not root.exists():
        return None
    project_path = normalize_path(context["project_root"])
    for candidate in root.glob("*-harness"):
        if is_link_like(candidate):
            raise HarnessError(f"Project Harness discovery found a linked candidate: {candidate}")
        manifest = read_json(candidate / "state" / "manifest.json", {})
        if (
            manifest.get("mode") == "single_lane"
            and manifest.get("project_root")
            and normalize_path(Path(manifest["project_root"])) == project_path
        ):
            validate_single_lane_predecessor(candidate, manifest, project_path)
            return candidate
    return None

def upgrade_single_lane_skill(
    predecessor: Path,
    destination: Path,
    context: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if destination.exists():
        raise HarnessError(f"Cannot upgrade over an existing project Harness: {destination}")
    manifest = read_json(predecessor / "state" / "manifest.json", {})
    old_id, old_links = validate_single_lane_predecessor(
        predecessor, manifest, normalize_path(context["project_root"]),
    )
    old_skill_name = predecessor.name
    created_links: list[Path] = []
    route_snapshots: dict[Path, bytes | None] = {}
    reject_tree_links(predecessor, "Single-Lane project Harness")
    shutil.copytree(predecessor, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    try:
        for path in destination.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if "state" in path.relative_to(destination).parts:
                continue
            content = path.read_text(encoding="utf-8")
            updated = content.replace(old_skill_name, context["skill_name"]).replace(old_id, context["project_id"])
            if updated != content:
                atomic_write_text(path, updated)
        links, created_links = ensure_runtime_links(context, args, destination)
        routes, route_snapshots = ensure_all_project_routes(context, destination)
        branch, commit = canonical_branch_and_commit(context)
        manifest_path = destination / "state" / "manifest.json"
        manifest = read_json(manifest_path, {})
        manifest.update({
            "project_id": context["project_id"],
            "project_name": context["project_name"],
            "project_root": str(primary_worktree_root(context)),
            "git_common_dir": str(context["git_common_dir"]),
            "mode": "multi_lane",
            "runtime_links": links,
            "updated_at": utc_now(),
        })
        atomic_write_json(manifest_path, manifest)
        atomic_write_json(
            registry_root(destination) / "baseline.json",
            {
                "schema_version": SCHEMA_VERSION,
                "canonical_root": str(primary_worktree_root(context)),
                "canonical_branch": branch,
                "canonical_commit": commit,
                "updated_at": utc_now(),
            },
        )
        if file_fingerprint(
            [path for path in (predecessor / "state" / "changes").rglob("*") if path.is_file()],
            predecessor / "state" / "changes",
        ) != file_fingerprint(
            [path for path in (destination / "state" / "changes").rglob("*") if path.is_file()],
            destination / "state" / "changes",
        ):
            raise HarnessError("Single-Lane upgrade changed Change evidence or INDEX bytes.")
        predecessor_results = predecessor / "state" / "evolution" / "results.tsv"
        destination_results = destination / "state" / "evolution" / "results.tsv"
        if predecessor_results.read_bytes() != destination_results.read_bytes():
            raise HarnessError("Single-Lane upgrade changed Evolution results bytes.")
    except Exception:
        restore_route_snapshots(route_snapshots)
        for link in reversed(created_links):
            remove_directory_link(link, destination)
        shutil.rmtree(destination, ignore_errors=True)
        raise
    for item in old_links:
        remove_directory_link(Path(item["path"]), predecessor)
    shutil.rmtree(predecessor)
    return {
        "status": "upgraded_single_lane",
        "from": str(predecessor),
        "skill_root": str(destination),
        "runtime_links": links,
        "routes": routes,
    }

@guard_project_skill
def project_migrate(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    root = skill_root_for(context, args)
    profile = audit = delta = architecture = bundle = None
    if getattr(args, "analysis_bundle", None):
        profile, audit, delta, architecture, bundle = load_analysis_bundle(args, context)
    if not (root / "state" / "manifest.json").exists():
        predecessor = find_single_lane_predecessor(context, args)
        init_result = (
            upgrade_single_lane_skill(predecessor, root, context, args)
            if predecessor
            else project_init(args)
        )
    else:
        init_result = None
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
    if (
        profile is not None
        and audit is not None
        and delta is not None
        and architecture is not None
        and (init_result is None or init_result.get("status") == "upgraded_single_lane")
    ):
        acquire_writer(root, "migration", context["project_id"])
        transaction: dict[str, Any] | None = None
        manifest_path = root / "state" / "manifest.json"
        manifest_snapshot = capture_file_snapshots((manifest_path,))
        candidate = root / "state" / "migration" / "staging" / context["project_id"]
        try:
            recover_content_transactions(root, "migration", context["project_id"])
            if candidate.exists():
                shutil.rmtree(candidate)
            candidate.parent.mkdir(parents=True, exist_ok=True)
            copy_non_state_skill(root, candidate)
            (candidate / "state").mkdir(parents=True, exist_ok=True)
            atomic_write_json(candidate / "state" / "manifest.json", read_json(manifest_path, {}))
            launchers = copy_runtime(candidate)
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
            candidate_check = knowledge_check_internal(candidate, context)
            if not candidate_check["healthy"]:
                raise HarnessError(f"Migration candidate knowledge validation failed: {candidate_check['findings']}")
            transaction = apply_content_transaction(
                root,
                candidate,
                "migration",
                context["project_id"],
                state_snapshot_paths=(manifest_path,),
            )
            links, new_links = ensure_runtime_links(context, args, root)
            created_links.extend(new_links)
            routes, route_snapshots = ensure_all_project_routes(context, root)
            manifest = read_json(manifest_path, {})
            manifest["analysis_status"] = profile.get("analysis_status")
            manifest["skill_revision"] = int(manifest.get("skill_revision", 1)) + 1
            manifest["host_runtime"] = "python"
            manifest["host_command"] = str(Path(sys.executable).resolve())
            manifest["launchers"] = launchers
            manifest["runtime_links"] = links
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
            restore_file_snapshots(manifest_snapshot)
            if candidate.exists():
                shutil.rmtree(candidate, ignore_errors=True)
            raise
        finally:
            release_writer(root, "migration", context["project_id"])
    else:
        links, _ = ensure_runtime_links(context, args, root)
        routes, _ = ensure_all_project_routes(context, root)
        manifest_path = root / "state" / "manifest.json"
        manifest = read_json(manifest_path, {})
        manifest["runtime_links"] = links
        manifest["updated_at"] = utc_now()
        atomic_write_json(manifest_path, manifest)
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
        links, _ = ensure_runtime_links(context, args, root)
        repaired_routes, _ = ensure_all_project_routes(context, root)
        manifest["runtime_links"] = links
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
    for link in manifest.get("runtime_links", []):
        path = Path(link["path"])
        if not path.exists() or not same_target(path, root):
            findings.append({"type": "broken_runtime_link", "runtime": link.get("runtime"), "path": str(path)})
    findings.extend(worktree_route_findings(context))
    for lane in records(registry_root(root) / "lanes"):
        worktree = Path(lane.get("worktree", ""))
        if lane.get("status") != "retired" and not worktree.exists():
            findings.append({"type": "stale_lane", "lane_id": lane.get("lane_id"), "worktree": str(worktree)})
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
        "runtime_links": manifest.get("runtime_links", []),
        "repaired_routes": repaired_routes,
    }

@guard_project_skill
def project_doctor(args: argparse.Namespace) -> dict[str, Any]:
    return project_doctor_internal(args)
