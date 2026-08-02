"""Project init, audit, portable migration, and doctor orchestration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
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
from .changes import contract_record_path, ecl_integrity_findings, rebuild_change_index
from .core import HarnessError, MANIFEST_SCHEMA_VERSION, SCHEMA_VERSION, atomic_write_json, atomic_write_text, git, git_baseline_relation, git_value, is_within, read_json, remove_owned_tree, run, safe_relative, stable_hash, utc_now
from .evolution import copy_non_state_skill
from .integration import load_integration_record
from .knowledge import SourceFingerprintSnapshot, context_source_fingerprints, knowledge_check_internal, rebuild_project_wiki_index
from .links import connector_route, copy_runtime, copy_scaffold, ensure_all_project_routes, ensure_runtime_links, generated_command_routes, remove_directory_link, restore_route_snapshots, same_target, worktree_route_findings
from .project import assign_project_identity, ensure_state, initial_manifest, project_context, require_skill, skill_root_for, worktree_roots
from .registry import records, registry_root
from .rendering import apply_creation_delta, install_analysis_bundle, load_focused_creation_bundle
from .transactions import acquire_writer, apply_content_transaction, capture_file_snapshots, commit_content_transaction, content_transaction_store, git_repository_findings, guard_project_skill, guard_project_skill_read_only, recover_content_transactions, release_writer, restore_file_snapshots, rollback_content_transaction, writer_lock_path

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
        fingerprint_snapshot = SourceFingerprintSnapshot(context)
        installed = install_analysis_bundle(
            skill_root,
            context,
            profile,
            audit,
            delta,
            architecture,
            bundle,
            bool(getattr(args, "allow_executable_artifacts", False)),
            fingerprint_snapshot,
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
    except Exception as exc:
        restore_route_snapshots(route_snapshots)
        for link in reversed(created_links):
            remove_directory_link(link, skill_root)
        if skill_root.exists():
            try:
                remove_owned_tree(skill_root, skill_root.parent, "Failed project Harness initialization")
            except Exception as cleanup_error:
                raise HarnessError(
                    f"Project initialization failed and owned cleanup was refused: {cleanup_error}"
                ) from exc
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


def normalize_portable_state(root: Path, context: dict[str, Any]) -> bool:
    index_rebuild_required = False
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
        if change.get("status") == "closing":
            change["status"] = "active"
            changed = True
            index_rebuild_required = True
        if change.get("integration_status") == "not_integrated" and not change.get("integrated_by"):
            change["integration_status"] = "not_requested"
            changed = True
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
    return index_rebuild_required

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
    focused_delta = None
    if getattr(args, "analysis_bundle", None):
        requested_bundle = Path(args.analysis_bundle).expanduser().resolve()
        full_names = ("project-profile.json", "audit.json", "creation-delta.json", "architecture.json")
        if all((requested_bundle / name).is_file() for name in full_names):
            profile, audit, delta, architecture, bundle = load_analysis_bundle(args, context)
        else:
            bundle = requested_bundle
            focused_delta = load_focused_creation_bundle(bundle, "migrate-focused")
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
    if profile is not None or focused_delta is not None or portable_upgrade or state_rebind:
        acquire_writer(root, "migration", context["project_id"])
        transaction: dict[str, Any] | None = None
        manifest_path = root / "state" / "manifest.json"
        snapshot_paths = [manifest_path, *sorted(registry_root(root).rglob("*.json"))]
        if state_rebind:
            snapshot_paths.append(root / "state" / "changes" / "INDEX.json")
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
                remove_owned_tree(candidate, candidate.parent, "Migration staging candidate")
            candidate.parent.mkdir(parents=True, exist_ok=True)
            copy_non_state_skill(root, candidate)
            (candidate / "state").mkdir(parents=True, exist_ok=True)
            atomic_write_json(
                candidate / "state" / "manifest.json",
                portable_manifest(read_json(manifest_path, {}), context),
            )
            launchers = copy_runtime(candidate)
            fingerprint_snapshot = SourceFingerprintSnapshot(context)
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
                    fingerprint_snapshot,
                )
            elif focused_delta is not None:
                applied = {
                    "mode": "focused",
                    "knowledge": {"refreshed": False},
                    "artifacts": apply_creation_delta(
                        candidate,
                        bundle,
                        focused_delta,
                        context,
                        bool(getattr(args, "allow_executable_artifacts", False)),
                        allow_retire=True,
                        fingerprint_snapshot=fingerprint_snapshot,
                    ),
                    "rules": {"affected_only": True},
                }
            else:
                applied = {"portable_state_upgrade": portable_upgrade, "lane_rebound": state_rebind}
                if state_rebind:
                    index_path = candidate / "references" / "project_wiki" / "index.json"
                    index = read_json(index_path, {})
                    for item in index.get("items", []):
                        sources = item.get("sources", [])
                        if isinstance(sources, list):
                            item["source_fingerprints"] = context_source_fingerprints(
                                context, sources, fingerprint_snapshot,
                            )
                    atomic_write_json(index_path, index)
            if profile is None and focused_delta is None:
                rebuild_project_wiki_index(candidate, context, snapshot=fingerprint_snapshot)
            if focused_delta is None:
                candidate_check = knowledge_check_internal(candidate, context, fingerprint_snapshot)
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
            lifecycle_changed = normalize_portable_state(root, context)
            if state_rebind or lifecycle_changed:
                rebuild_change_index(root)
            manifest = read_json(manifest_path, {})
            if profile is not None:
                manifest["analysis_status"] = profile.get("analysis_status")
            manifest["skill_revision"] = int(manifest.get("skill_revision", 1)) + 1
            manifest["launchers"] = launchers
            manifest["updated_at"] = utc_now()
            atomic_write_json(manifest_path, manifest)
            commit_content_transaction(transaction)
            transaction = None
        except Exception as exc:
            restore_route_snapshots(route_snapshots)
            for link in reversed(created_links):
                remove_directory_link(link, root)
            if transaction is not None:
                rollback_content_transaction(transaction)
            restore_file_snapshots(state_snapshots)
            if candidate.exists():
                try:
                    remove_owned_tree(candidate, candidate.parent, "Migration staging candidate")
                except Exception as cleanup_error:
                    raise HarnessError(
                        f"Migration failed and candidate cleanup was refused: {cleanup_error}"
                    ) from exc
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


def local_state_initialized(skill_root: Path) -> bool:
    required = (
        "state/registry/lanes",
        "state/registry/changes",
        "state/registry/contracts",
        "state/registry/integrations",
        "state/registry/locks",
        "state/changes/active",
        "state/changes/parking",
        "state/changes/archive",
        "state/changes/INDEX.json",
        "state/registry/baseline.json",
        "state/evolution/state.json",
        "state/evolution/results.tsv",
    )
    return all((skill_root / relative).exists() for relative in required)


def project_skill_git_boundary(context: dict[str, Any], root: Path) -> dict[str, Any]:
    metadata = root / ".git"
    enabled = metadata.exists() or metadata.is_symlink()
    if not enabled:
        return {"enabled": False, "boundary_healthy": True, "findings": []}
    findings = git_repository_findings(root)
    tracked_state = git(root, "ls-files", "-z", "--", "state", check=False)
    if tracked_state.returncode != 0:
        findings.append({"type": "unreadable_skill_git_tracked_state"})
    else:
        disallowed = sorted(
            value for value in tracked_state.stdout.split("\0")
            if value and value.replace("\\", "/") != "state/manifest.json"
        )
        if disallowed:
            findings.append({"type": "tracked_local_skill_state", "paths": disallowed})
    ignored_state = git(
        root, "check-ignore", "-q", "--no-index", "--", "state/changes/.boundary-probe",
        check=False,
    )
    if ignored_state.returncode != 0:
        findings.append({"type": "local_skill_state_not_ignored"})
    manifest_ignored = git(
        root, "check-ignore", "-q", "--no-index", "--", "state/manifest.json",
        check=False,
    )
    if manifest_ignored.returncode == 0:
        findings.append({"type": "portable_manifest_ignored"})
    if context.get("mode") == "multi_lane":
        skill_relative = f".agents/skills/{context['skill_name']}"
        claude_relative = f".claude/skills/{context['skill_name']}"
        tracked = git(
            context["project_root"],
            "ls-files", "--stage", "--", skill_relative, claude_relative,
            check=False,
        )
        if tracked.returncode != 0:
            findings.append({"type": "unreadable_outer_git_index"})
        elif tracked.stdout.strip():
            entries = [line for line in tracked.stdout.splitlines() if line.strip()]
            finding_type = (
                "project_skill_tracked_as_submodule"
                if any(line.startswith("160000 ") for line in entries)
                else "project_skill_tracked_by_business_repository"
            )
            findings.append({"type": finding_type, "entries": entries})
        exclude_path = context["git_common_dir"] / "info" / "exclude"
        exclude_lines = (
            exclude_path.read_text(encoding="utf-8").splitlines()
            if exclude_path.is_file()
            else []
        )
        required_excludes = [f"/{skill_relative}", f"/{claude_relative}"]
        missing_excludes = [value for value in required_excludes if value not in exclude_lines]
        if missing_excludes:
            findings.append({
                "type": "outer_project_skill_not_ignored",
                "path": skill_relative,
                "missing_excludes": missing_excludes,
            })
        shared_routes = git(
            context["project_root"],
            "ls-files", "-z", "--", "AGENTS.md", "CLAUDE.md", "scripts/harness-skill-link.*",
            check=False,
        )
        tracked_routes = set(shared_routes.stdout.split("\0")) if shared_routes.returncode == 0 else set()
        missing_routes = [name for name in ("AGENTS.md", "CLAUDE.md") if name not in tracked_routes]
        if not any(value.startswith("scripts/harness-skill-link.") for value in tracked_routes):
            missing_routes.append("scripts/harness-skill-link.<host>")
        if missing_routes:
            findings.append({"type": "unshared_business_project_route", "paths": missing_routes})
    return {"enabled": True, "boundary_healthy": not findings, "findings": findings}

def project_doctor_internal(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    root = require_skill(context, args)
    manifest = read_json(root / "state" / "manifest.json", {})
    findings = []
    repaired_routes = None
    initialized_paths: list[str] = []
    if getattr(args, "repair_links", False):
        initialized_paths = ensure_state(root, context, getattr(args, "canonical_branch", None))
        if "state/changes/INDEX.json" in initialized_paths and records(registry_root(root) / "changes"):
            rebuild_change_index(root)
        ensure_runtime_links(context, args, root)
        repaired_routes, _ = ensure_all_project_routes(context, root)
    state_ready = local_state_initialized(root)
    if not state_ready:
        findings.append({"type": "local_state_uninitialized"})
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
    baseline_relation = "not_applicable"
    if context.get("mode") == "multi_lane" and context.get("branch") == baseline.get("canonical_branch"):
        baseline_relation = git_baseline_relation(
            context["project_root"], baseline.get("canonical_commit"), context.get("head"),
        )
        finding_types = {
            "worktree_behind": "canonical_worktree_behind",
            "diverged": "canonical_baseline_diverged",
            "unavailable": "canonical_baseline_unavailable",
        }
        if baseline_relation in finding_types:
            findings.append({
                "type": finding_types[baseline_relation],
                "recorded": baseline.get("canonical_commit"),
                "current": context.get("head"),
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
    git_sharing = project_skill_git_boundary(context, root)
    findings.extend(git_sharing["findings"])
    return {
        "healthy": not findings,
        "findings": findings,
        "baseline": {
            "relation": baseline_relation,
            "recorded": baseline.get("canonical_commit"),
            "current": context.get("head"),
            "canonical_branch": baseline.get("canonical_branch"),
        },
        "runtime_links": [],
        "repaired_routes": repaired_routes,
        "local_state": {
            "initialized": state_ready,
            "created": initialized_paths,
        },
        "git_sharing": git_sharing,
    }

@guard_project_skill
def project_doctor(args: argparse.Namespace) -> dict[str, Any]:
    return project_doctor_internal(args)
