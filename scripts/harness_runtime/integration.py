"""Exact-range Integration, independent review, I2 landing, and recovery."""

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

from .changes import change_record_path, contract_record_path, load_change_record, load_contract_record
from .core import HarnessError, SCHEMA_VERSION, atomic_create_json, atomic_write_json, canonical_id, git, git_baseline_relation, git_value, is_within, read_json, safe_relative, stable_hash, tree_junctions, utc_now
from .links import detach_worktree_links
from .project import project_context, require_skill
from .registry import bound_records, lane_id, registry_root
from .reviews import validate_integration_review
from .transactions import acquire_writer, guard_project_skill, release_writer, writer_lock_path

def integration_record_path(skill_root: Path, integration_id: str) -> Path:
    identifier = canonical_id(integration_id, "Integration id")
    return registry_root(skill_root) / "integrations" / f"{identifier}.json"

def load_integration_record(skill_root: Path, integration_id: str, *, required: bool = False) -> dict[str, Any]:
    identifier = canonical_id(integration_id, "Integration id")
    value = read_json(integration_record_path(skill_root, identifier), {})
    if not value:
        if required:
            raise HarnessError(f"Unknown Integration: {identifier}")
        return {}
    if not isinstance(value, dict) or value.get("integration_id") != identifier:
        raise HarnessError(f"Integration record id mismatch: {identifier}")
    change_ids = value.get("change_ids", [])
    if not isinstance(change_ids, list):
        raise HarnessError(f"Integration record has invalid change_ids: {identifier}")
    for change_id in change_ids:
        if canonical_id(change_id, "Integration Change id") != change_id:
            raise HarnessError(f"Integration record has non-canonical Change id: {identifier}")
    return value

def integration_records(skill_root: Path) -> list[dict[str, Any]]:
    return bound_records(registry_root(skill_root) / "integrations", "integration_id", "Integration")

def integration_review_report(
    report_path: str,
    record: dict[str, Any],
    candidate_commit: str,
) -> dict[str, Any]:
    try:
        return validate_integration_review(report_path, record, candidate_commit, canonical_id)
    except ValueError as exc:
        raise HarnessError(str(exc)) from exc

def refresh_baseline_from_canonical(
    skill_root: Path,
    context: dict[str, Any],
) -> dict[str, Any]:
    path = registry_root(skill_root) / "baseline.json"
    baseline = read_json(path, {})
    canonical_branch = baseline.get("canonical_branch")
    if context.get("branch") != canonical_branch:
        return baseline
    if git(context["project_root"], "status", "--porcelain").stdout.strip():
        raise HarnessError("Canonical worktree must be clean before Integration starts.")
    current = context.get("head")
    previous = baseline.get("canonical_commit")
    if current and previous and current != previous:
        relation = git_baseline_relation(context["project_root"], previous, current)
        if relation != "canonical_advanced":
            raise HarnessError(
                f"Canonical branch relation to the Registry baseline is {relation}; audit it before Integration."
            )
        baseline["canonical_commit"] = current
        baseline["updated_at"] = utc_now()
        atomic_write_json(path, baseline)
    return baseline

def exact_change_commits(project_root: Path, change: dict[str, Any]) -> list[str]:
    base = change.get("base_commit")
    completion = change.get("completion_commit")
    if not base or not completion:
        raise HarnessError(f"Change has no exact base/completion range: {change.get('change_id')}")
    if git(project_root, "cat-file", "-e", f"{base}^{{commit}}", check=False).returncode != 0:
        raise HarnessError(f"Base commit is unavailable for {change.get('change_id')}: {base}")
    if git(project_root, "cat-file", "-e", f"{completion}^{{commit}}", check=False).returncode != 0:
        raise HarnessError(f"Completion commit is unavailable: {completion}")
    if git(project_root, "merge-base", "--is-ancestor", base, completion, check=False).returncode != 0:
        raise HarnessError(f"Completion commit is not descended from base for {change.get('change_id')}.")
    output = git(project_root, "rev-list", "--reverse", "--topo-order", f"{base}..{completion}").stdout
    commits = [line.strip() for line in output.splitlines() if line.strip()]
    if not commits:
        raise HarnessError(f"Change has an empty commit range: {change.get('change_id')}")
    for commit in commits:
        parent_line = git(project_root, "rev-list", "--parents", "-n", "1", commit).stdout.split()
        if len(parent_line) > 2:
            raise HarnessError(
                f"Change {change.get('change_id')} contains merge commit {commit}; use a linear Change range."
            )
    return commits

def parse_completion_commit_overrides(values: list[str], change_ids: set[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        change_id, separator, commit = value.partition("=")
        if not separator or not commit.strip():
            raise HarnessError("Integration completion commits must use <change-id>=<sha>.")
        identifier = canonical_id(change_id.strip(), "Integration completion Change id")
        if identifier not in change_ids:
            raise HarnessError(f"Completion commit was provided for an unselected Change: {identifier}")
        if identifier in overrides:
            raise HarnessError(f"Completion commit was provided more than once for Change: {identifier}")
        overrides[identifier] = commit.strip()
    return overrides

def order_changes_for_integration(skill_root: Path, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["change_id"]: item for item in selected}
    remaining = list(selected)
    ordered: list[dict[str, Any]] = []
    ordered_ids: set[str] = set()
    while remaining:
        progressed = False
        for item in list(remaining):
            contract = load_contract_record(skill_root, item["change_id"])
            dependencies = set(contract.get("depends_on_changes", []))
            missing = dependencies - set(by_id)
            unresolved = [
                change_id for change_id in missing
                if not load_change_record(skill_root, change_id).get("integrated_by")
            ]
            if unresolved:
                raise HarnessError(
                    f"Change {item['change_id']} has unintegrated dependencies: {', '.join(sorted(unresolved))}"
                )
            if dependencies & set(by_id) <= ordered_ids:
                ordered.append(item)
                ordered_ids.add(item["change_id"])
                remaining.remove(item)
                progressed = True
        if not progressed:
            cycle = ", ".join(item["change_id"] for item in remaining)
            raise HarnessError(f"Integration dependency cycle or invalid order among: {cycle}")
    return ordered

def validated_integration_worktree(skill_root: Path, record: dict[str, Any]) -> Path:
    allowed_root = (skill_root / "state" / "integrations").resolve()
    relative = safe_relative(str(record.get("worktree", "")), "Integration worktree")
    worktree = (skill_root / relative).resolve()
    if not is_within(worktree, allowed_root):
        raise HarnessError("Integration Record points outside the managed Integration root.")
    integration_id = canonical_id(record.get("integration_id", ""), "Integration id")
    if record.get("integration_id") != integration_id:
        raise HarnessError("Integration Record contains a non-canonical id.")
    expected_branch = f"integration/{integration_id}"
    if record.get("branch") != expected_branch:
        raise HarnessError("Integration Record branch does not match its id.")
    return worktree

def remove_integration_worktree(
    context: dict[str, Any],
    skill_root: Path,
    worktree: Path,
) -> dict[str, dict[str, str]]:
    detached = detach_worktree_links(worktree, skill_root)
    junctions = tree_junctions(worktree)
    if junctions:
        relative = [path.relative_to(worktree).as_posix() for path in junctions]
        raise HarnessError(
            "Integration worktree still contains directory junctions after Harness detach: "
            + ", ".join(relative)
        )
    result = git(context["project_root"], "worktree", "remove", str(worktree), check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise HarnessError(f"Git could not remove the Integration worktree: {detail}")
    return detached

@guard_project_skill
def integrate_start(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    if context["mode"] != "multi_lane":
        raise HarnessError("Integration is unavailable in single-Lane non-Git mode.")
    skill_root = require_skill(context, args)
    integration_id = canonical_id(args.integration_id, "Integration id")
    record_path = integration_record_path(skill_root, integration_id)
    if record_path.exists():
        raise HarnessError(f"Integration id already exists: {integration_id}")
    change_ids = [canonical_id(item, "Change id") for item in args.change_ids]
    if len(set(change_ids)) != len(change_ids):
        raise HarnessError("Integration Change ids must be unique.")
    overrides = parse_completion_commit_overrides(args.completion_commit, set(change_ids))
    selected = []
    for change_id in change_ids:
        value = load_change_record(skill_root, change_id, required=True)
        if (
            not value
            or value.get("status") != "completed"
            or not value.get("validation_passed")
            or not value.get("evidence_complete")
        ):
            raise HarnessError(f"Change is not integration-ready: {change_id}")
        if value.get("integrated_by"):
            raise HarnessError(f"Change is already integrated: {change_id}")
        stored_commit = value.get("completion_commit")
        override = overrides.get(change_id)
        stored_resolved = (
            git_value(context["project_root"], "rev-parse", "--verify", f"{stored_commit}^{{commit}}")
            if stored_commit else None
        )
        override_resolved = (
            git_value(context["project_root"], "rev-parse", "--verify", f"{override}^{{commit}}")
            if override else None
        )
        if stored_commit and not stored_resolved:
            raise HarnessError(f"Recorded completion commit is unavailable for Change: {change_id}")
        if override and not override_resolved:
            raise HarnessError(f"Completion commit is unavailable for Change {change_id}: {override}")
        if stored_resolved and override_resolved and stored_resolved != override_resolved:
            raise HarnessError(f"Completion commit conflicts with the boundary recorded for Change: {change_id}")
        completion = stored_resolved or override_resolved
        if not completion:
            raise HarnessError(
                f"Change has no Integration commit boundary: {change_id}. "
                "Provide --completion-commit <change-id>=<sha> when starting Integration."
            )
        selected_value = dict(value)
        selected_value["completion_commit"] = completion
        selected.append(selected_value)
    selected = order_changes_for_integration(skill_root, selected)
    baseline = refresh_baseline_from_canonical(skill_root, context)
    base_commit = baseline.get("canonical_commit") or context["head"]
    ranges = {item["change_id"]: exact_change_commits(context["project_root"], item) for item in selected}
    flattened = [commit for item in selected for commit in ranges[item["change_id"]]]
    if len(flattened) != len(set(flattened)):
        raise HarnessError("Selected Change commit ranges overlap; split or rebase them before Integration.")
    temp_root = skill_root / "state" / "integrations"
    temp_root.mkdir(parents=True, exist_ok=True)
    worktree = temp_root / integration_id
    branch = f"integration/{integration_id}"
    record = {
        "schema_version": SCHEMA_VERSION,
        "integration_id": integration_id,
        "status": "preparing",
        "canonical_base": base_commit,
        "canonical_branch": baseline.get("canonical_branch"),
        "change_ids": [item["change_id"] for item in selected],
        "completion_commits": [item["completion_commit"] for item in selected],
        "change_commit_ranges": ranges,
        "applied_commits": [],
        "remaining_commits": flattened,
        "worktree": worktree.relative_to(skill_root).as_posix(),
        "branch": branch,
        "integrator_id": lane_id(context),
        "conflicts": [],
        "integrator_edits": [],
        "validation": [],
        "review": None,
        "review_report": None,
        "landing_commit": None,
        "landing_candidate_commit": None,
        "landing_phase": "not_started",
        "last_error": None,
        "candidate_commit": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    atomic_create_json(record_path, record)
    try:
        git(context["project_root"], "worktree", "add", "-b", branch, str(worktree), str(base_commit))
    except Exception as exc:
        record["status"] = "preparing_failed"
        record["last_error"] = str(exc)
        record["updated_at"] = utc_now()
        atomic_write_json(record_path, record)
        raise
    try:
        for item in selected:
            for commit in ranges[item["change_id"]]:
                result = git(worktree, "cherry-pick", commit, check=False)
                if result.returncode != 0:
                    record["status"] = "conflict"
                    record["conflicts"].append({
                        "change_id": item["change_id"], "commit": commit,
                        "head_before_conflict": git_value(worktree, "rev-parse", "HEAD"),
                        "detail": (result.stderr or result.stdout).strip(),
                    })
                    break
                record["applied_commits"].append(commit)
                record["remaining_commits"].remove(commit)
            if record["status"] == "conflict":
                break
        if record["status"] != "conflict":
            record["status"] = "ready_for_review"
            record["candidate_commit"] = git_value(worktree, "rev-parse", "HEAD")
    finally:
        record["updated_at"] = utc_now()
        atomic_write_json(record_path, record)
    return {**record, "worktree": str(worktree)}

def resume_integration(skill_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    if record.get("status") != "conflict":
        raise HarnessError("Only a conflict Integration can be resumed.")
    worktree = validated_integration_worktree(skill_root, record)
    if not worktree.exists():
        raise HarnessError("Integration worktree is missing.")
    unresolved = git(worktree, "diff", "--name-only", "--diff-filter=U", check=False).stdout.strip()
    if unresolved:
        raise HarnessError(f"Integration still has unresolved conflicts:\n{unresolved}")
    if git_value(worktree, "rev-parse", "--verify", "CHERRY_PICK_HEAD"):
        raise HarnessError("Run git cherry-pick --continue after resolving the current conflict.")
    if git(worktree, "status", "--porcelain").stdout.strip():
        raise HarnessError("Commit the resolved conflict before resuming Integration.")
    last_conflict = record.get("conflicts", [])[-1]
    if git_value(worktree, "rev-parse", "HEAD") == last_conflict.get("head_before_conflict"):
        raise HarnessError("The conflicted commit was not completed; resolve and commit it before resume.")
    conflicted = last_conflict.get("commit")
    if conflicted in record.get("remaining_commits", []):
        record["remaining_commits"].remove(conflicted)
        record["applied_commits"].append(conflicted)
    record["status"] = "applying"
    while record.get("remaining_commits"):
        commit = record["remaining_commits"][0]
        result = git(worktree, "cherry-pick", commit, check=False)
        if result.returncode != 0:
            record["status"] = "conflict"
            record["conflicts"].append({
                "change_id": None, "commit": commit,
                "head_before_conflict": git_value(worktree, "rev-parse", "HEAD"),
                "detail": (result.stderr or result.stdout).strip(),
            })
            break
        record["remaining_commits"].pop(0)
        record["applied_commits"].append(commit)
    if not record.get("remaining_commits"):
        record["status"] = "ready_for_review"
        record["candidate_commit"] = git_value(worktree, "rev-parse", "HEAD")
    record["updated_at"] = utc_now()
    atomic_write_json(integration_record_path(skill_root, record["integration_id"]), record)
    return {**record, "worktree": str(worktree)}

@guard_project_skill
def integrate_status(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    if args.integration_id:
        integration_id = canonical_id(args.integration_id, "Integration id")
        value = load_integration_record(skill_root, integration_id, required=True)
        if args.resume:
            value = resume_integration(skill_root, value)
        return {"integration": value}
    if args.resume:
        raise HarnessError("--resume requires --integration-id.")
    return {"integrations": integration_records(skill_root)}

def integration_contract_snapshots(skill_root: Path, change_ids: list[str]) -> list[dict[str, Any]]:
    snapshots = []
    for change_id in change_ids:
        contract = load_contract_record(skill_root, change_id)
        if contract:
            snapshot = json.loads(json.dumps(contract))
            snapshot["status"] = "integrated"
            snapshots.append(snapshot)
    return snapshots

def commit_integration_registry(
    skill_root: Path,
    context: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    landing = record["landing_commit"]
    previous = record.get("canonical_base")
    affected_paths = sorted(set(
        git(context["project_root"], "diff", "--name-only", previous, landing).stdout.splitlines()
    ))
    contract_snapshots = integration_contract_snapshots(skill_root, record["change_ids"])
    for change_id in record["change_ids"]:
        change_path = change_record_path(skill_root, change_id)
        change = load_change_record(skill_root, change_id, required=True)
        change["integrated_by"] = record["integration_id"]
        change["integration_status"] = "integrated"
        change["updated_at"] = utc_now()
        atomic_write_json(change_path, change)
        contract_path = contract_record_path(skill_root, change_id)
        contract = load_contract_record(skill_root, change_id)
        if contract:
            contract["status"] = "integrated"
            contract["updated_at"] = utc_now()
            atomic_write_json(contract_path, contract)
    record["evolution_signals"] = {
        "conflicts": record.get("conflicts", []),
        "integrator_edits": record.get("integrator_edits", []),
        "contracts": [item["change_id"] for item in contract_snapshots],
        "knowledge_refresh_deferred_to_evolution": True,
    }
    event_id = f"{record['integration_id']}-{stable_hash(landing, 12)}"
    atomic_write_json(
        registry_root(skill_root) / "baseline-events" / f"{event_id}.json",
        {
            "schema_version": SCHEMA_VERSION,
            "event": "canonical-baseline-advanced",
            "integration_id": record["integration_id"],
            "previous_canonical_commit": previous,
            "canonical_commit": landing,
            "change_ids": record["change_ids"],
            "affected_paths": affected_paths,
            "contracts": contract_snapshots,
            "knowledge_status": "refresh-needed-for-affected-scopes",
            "knowledge_refresh_deferred_to_evolution": True,
            "evolution_signals": record["evolution_signals"],
            "updated_at": utc_now(),
        },
    )
    baseline_path = registry_root(skill_root) / "baseline.json"
    baseline = read_json(baseline_path, {})
    baseline["canonical_commit"] = landing
    baseline["updated_at"] = utc_now()
    atomic_write_json(baseline_path, baseline)
    return {
        "affected_paths": affected_paths,
        "contract_snapshots": contract_snapshots,
        "event_id": event_id,
    }

def persist_integration_recovery(
    path: Path,
    record: dict[str, Any],
    error: Exception,
    phase: str,
) -> None:
    record["status"] = "landing_recovery_required" if phase != "pre_merge" else "ready_for_review"
    record["landing_phase"] = phase
    record["last_error"] = str(error)
    record["updated_at"] = utc_now()
    try:
        atomic_write_json(path, record)
    except Exception:
        pass

@guard_project_skill
def integrate_complete(args: argparse.Namespace) -> dict[str, Any]:
    if not args.confirm_i2:
        raise HarnessError("Integration completion requires explicit --confirm-i2.")
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    integration_id = canonical_id(args.integration_id, "Integration id")
    path = integration_record_path(skill_root, integration_id)
    record = load_integration_record(skill_root, integration_id, required=True)
    if record.get("status") == "integrated":
        current = git_value(context["project_root"], "rev-parse", "HEAD")
        if current != record.get("landing_commit"):
            raise HarnessError("Integration is recorded as landed but canonical HEAD no longer matches it.")
        writer = read_json(writer_lock_path(skill_root) / "owner.json", {})
        if writer.get("kind") == "integration" and writer.get("owner_id") == integration_id:
            release_writer(skill_root, "integration", integration_id)
        return {"status": "already_integrated", "landing_commit": current, "record": record}
    phase = record.get("landing_phase", "not_started")
    if record.get("status") == "conflict" and phase in {"not_started", "pre_merge"}:
        conflict_worktree = validated_integration_worktree(skill_root, record)
        unresolved = git(conflict_worktree, "diff", "--name-only", "--diff-filter=U", check=False).stdout.strip()
        if unresolved:
            raise HarnessError(f"Integration still has unresolved conflicts:\n{unresolved}")
        if (conflict_worktree / ".git").exists() and git_value(conflict_worktree, "rev-parse", "--verify", "CHERRY_PICK_HEAD"):
            raise HarnessError("Finish the current cherry-pick before completing Integration.")
    if record.get("remaining_commits") and phase in {"not_started", "pre_merge"}:
        raise HarnessError(
            "Integration has unapplied commits after a conflict; apply the recorded remaining commits before completion."
        )
    validation = args.validation or record.get("validation", [])
    review_report = record.get("review_report")
    validation_passed = bool(args.validation_passed or record.get("validation_passed"))
    if not validation or not validation_passed:
        raise HarnessError("Integration requires passing aggregate validation evidence.")
    worktree = validated_integration_worktree(skill_root, record)
    integration_head = record.get("landing_candidate_commit")
    if phase in {"not_started", "pre_merge"}:
        if not worktree.exists():
            raise HarnessError("Integration worktree is missing before canonical landing.")
        dirty = git(worktree, "status", "--porcelain").stdout.strip()
        if dirty:
            raise HarnessError("Commit Integrator edits and validation evidence before completion.")
        integration_head = git_value(worktree, "rev-parse", "HEAD")
        if not integration_head:
            raise HarnessError("Integration worktree has no candidate commit.")
        if not args.review_report:
            raise HarnessError("I2 requires --review-report for the independently reviewed candidate.")
        review_report = integration_review_report(args.review_report, record, integration_head)
        reviewed_commit = integration_head
    elif args.review_report:
        review_report = integration_review_report(args.review_report, record, record.get("reviewed_commit", ""))
        reviewed_commit = review_report["reviewed_commit"]
    else:
        reviewed_commit = record.get("reviewed_commit")
    if not review_report:
        raise HarnessError("Integration requires a bound independent review report before I2.")
    if not integration_head:
        raise HarnessError("Integration recovery record has no landing candidate commit.")
    canonical_branch = record.get("canonical_branch")
    if not canonical_branch:
        raise HarnessError("Canonical branch is unknown; update baseline before completing Integration.")
    current_branch = git_value(context["project_root"], "branch", "--show-current")
    if current_branch != canonical_branch:
        raise HarnessError(f"Run complete from the canonical worktree on branch {canonical_branch}.")
    if git(context["project_root"], "status", "--porcelain").stdout.strip():
        raise HarnessError("Canonical worktree must be clean before I2 landing.")
    acquire_writer(skill_root, "integration", record["integration_id"])
    try:
        if phase in {"not_started", "pre_merge"}:
            record["status"] = "landing"
            record["landing_phase"] = "pre_merge"
            record["landing_candidate_commit"] = integration_head
            record["reviewed_commit"] = reviewed_commit
            record["validation"] = validation
            record["validation_passed"] = True
            record["review"] = review_report.get("verdict")
            record["review_report"] = review_report
            candidate = record.get("candidate_commit") or record.get("canonical_base")
            record["integrator_commits"] = (
                []
                if candidate == integration_head
                else git(
                    worktree, "rev-list", "--reverse", f"{candidate}..{integration_head}",
                ).stdout.splitlines()
            )
            record["integrator_edits"] = sorted(set(
                git(worktree, "diff", "--name-only", candidate, integration_head).stdout.splitlines()
            )) if record["integrator_commits"] else []
            record["last_error"] = None
            record["updated_at"] = utc_now()
            atomic_write_json(path, record)
            phase = "pre_merge"
            canonical_head = git_value(context["project_root"], "rev-parse", "HEAD")
            if canonical_head == integration_head:
                landing = integration_head
            elif canonical_head == record.get("canonical_base"):
                git(context["project_root"], "merge", "--ff-only", integration_head)
                landing = git_value(context["project_root"], "rev-parse", "HEAD")
            else:
                raise HarnessError("Canonical HEAD changed after Integration review; restart or audit the landing.")
            if landing != integration_head:
                raise HarnessError("Canonical landing did not produce the reviewed Integration commit.")
            record["landing_commit"] = landing
            record["landing_phase"] = "canonical_landed"
            record["status"] = "landing_recovery_required"
            record["updated_at"] = utc_now()
            atomic_write_json(path, record)
            phase = "canonical_landed"

        if phase == "canonical_landed":
            canonical_head = git_value(context["project_root"], "rev-parse", "HEAD")
            if canonical_head != record.get("landing_commit"):
                raise HarnessError("Canonical HEAD no longer matches the recorded landed Integration commit.")
            registry_result = commit_integration_registry(skill_root, context, record)
            record["registry_result"] = registry_result
            record["landing_phase"] = "registry_committed"
            record["status"] = "landing_recovery_required"
            record["updated_at"] = utc_now()
            atomic_write_json(path, record)
            phase = "registry_committed"

        if phase == "registry_committed":
            if worktree.exists():
                remove_integration_worktree(context, skill_root, worktree)
            git(context["project_root"], "branch", "-d", record["branch"], check=False)
            record["landing_phase"] = "cleanup_complete"
            record["status"] = "integrated"
            record["last_error"] = None
            record["updated_at"] = utc_now()
            atomic_write_json(path, record)
            phase = "cleanup_complete"
        if phase == "cleanup_complete" and record.get("status") != "integrated":
            record["status"] = "integrated"
            record["last_error"] = None
            record["updated_at"] = utc_now()
            atomic_write_json(path, record)
        release_writer(skill_root, "integration", record["integration_id"])
        return {"status": "integrated", "landing_commit": record["landing_commit"], "record": record}
    except Exception as exc:
        canonical_head = git_value(context["project_root"], "rev-parse", "HEAD")
        landed = bool(
            record.get("landing_commit")
            or canonical_head == integration_head
            or phase in {"canonical_landed", "registry_committed", "cleanup_complete"}
        )
        if landed:
            record["landing_commit"] = record.get("landing_commit") or integration_head
            recovery_phase = phase if phase != "pre_merge" else "canonical_landed"
            persist_integration_recovery(path, record, exc, recovery_phase)
        else:
            persist_integration_recovery(path, record, exc, "pre_merge")
            release_writer(skill_root, "integration", record["integration_id"])
        raise HarnessError(f"Integration landing failed during {record.get('landing_phase')}: {exc}") from exc

@guard_project_skill
def integrate_abort(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    integration_id = canonical_id(args.integration_id, "Integration id")
    path = integration_record_path(skill_root, integration_id)
    record = load_integration_record(skill_root, integration_id, required=True)
    canonical_head = git_value(context["project_root"], "rev-parse", "HEAD")
    landed_candidate = record.get("landing_candidate_commit")
    if (
        record.get("landing_phase", "not_started") not in {"not_started", "pre_merge"}
        or (landed_candidate and canonical_head == landed_candidate)
    ):
        raise HarnessError("A canonically landed Integration cannot be aborted; resume completion instead.")
    worktree = validated_integration_worktree(skill_root, record)
    if worktree.exists():
        git(worktree, "merge", "--abort", check=False)
        git(worktree, "cherry-pick", "--abort", check=False)
        try:
            remove_integration_worktree(context, skill_root, worktree)
        except Exception as exc:
            record["last_error"] = str(exc)
            record["updated_at"] = utc_now()
            atomic_write_json(path, record)
            raise
    if record.get("branch"):
        git(context["project_root"], "branch", "-D", record["branch"], check=False)
    record["status"] = "aborted"
    record["updated_at"] = utc_now()
    atomic_write_json(path, record)
    lock = read_json(writer_lock_path(skill_root) / "owner.json", {})
    if lock.get("kind") == "integration" and lock.get("owner_id") == record.get("integration_id"):
        release_writer(skill_root, "integration", record["integration_id"])
    return {"status": "aborted", "integration_id": integration_id}
