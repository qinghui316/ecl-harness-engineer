"""E1 ownership, candidate staging, Judge gates, publication, and results."""

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
from .changes import evolve_check_internal, evolve_check_locked
from .contracts import load_audit_rubric
from .core import HarnessError, SCHEMA_VERSION, atomic_append_tsv, atomic_write_json, canonical_id, is_link_like, read_json, reject_tree_links, remove_owned_tree, utc_now
from .knowledge import SourceFingerprintSnapshot, canonical_knowledge_finding_type, knowledge_check_internal
from .project import project_context, require_skill
from .rendering import apply_creation_delta, install_analysis_bundle
from .reviews import validate_evolution_judge
from .transactions import CONTENT_TRANSACTION_PATHS, acquire_writer, apply_content_transaction, capture_file_snapshots, commit_content_transaction, guard_project_skill, recover_content_transactions, release_writer, restore_file_snapshots, rollback_content_transaction, short_registry_lock, writer_lock_path

@guard_project_skill
def evolve_status(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    state = read_json(skill_root / "state" / "evolution" / "state.json", {})
    owner = skill_root / "state" / "registry" / "locks" / "evolution-owner"
    return {
        "state": state,
        "owner_claimed": owner.exists(),
        "writer": read_json(writer_lock_path(skill_root) / "owner.json", None),
        "pending_path": str(skill_root / "state" / "evolution" / "pending.json"),
    }

def harness_content_fingerprint(skill_root: Path) -> str:
    digest = hashlib.sha256()
    for owner in CONTENT_TRANSACTION_PATHS:
        root = skill_root / owner
        paths = [root] if root.is_file() else sorted(root.rglob("*"), key=lambda item: item.as_posix()) if root.is_dir() else []
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(skill_root)
            if "__pycache__" in relative.parts or path.suffix == ".pyc":
                continue
            digest.update(relative.as_posix().encode("utf-8"))
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(64 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def candidate_binding_fingerprint(content_fingerprint: str, source_snapshot_digest: str) -> str:
    return hashlib.sha256(
        f"{content_fingerprint}\0{source_snapshot_digest}".encode("ascii")
    ).hexdigest()

def evolution_owner_record(skill_root: Path) -> dict[str, Any]:
    return read_json(
        skill_root / "state" / "registry" / "locks" / "evolution-owner" / "owner.json",
        {},
    )

def require_evolution_owner(skill_root: Path, owner_id: str | None = None) -> dict[str, Any]:
    owner = evolution_owner_record(skill_root)
    if not owner:
        raise HarnessError("Evolution requires an active E1 owner claim.")
    if owner_id and owner.get("owner") != owner_id:
        raise HarnessError("Evolution owner id does not match the active claim.")
    writer = read_json(writer_lock_path(skill_root) / "owner.json", {})
    if writer.get("kind") != "evolution" or writer.get("owner_id") != owner.get("owner"):
        raise HarnessError("Evolution does not own the shared project Harness writer lock.")
    return owner

def copy_non_state_skill(source: Path, destination: Path) -> None:
    if is_link_like(source):
        raise HarnessError(f"Project Harness content source must be physical: {source}")
    destination.mkdir(parents=True, exist_ok=False)
    for name in CONTENT_TRANSACTION_PATHS:
        item = source / name
        if not item.exists():
            continue
        target = destination / name
        if item.is_dir():
            reject_tree_links(item, f"Project Harness content source {name}")
            shutil.copytree(
                item,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(item, target)


def protect_audit_rubric(current: Path, candidate: Path) -> None:
    relative = Path("references") / "audit-rubric.json"
    current_path = current / relative
    candidate_path = candidate / relative
    if not current_path.is_file() or not candidate_path.is_file():
        raise HarnessError("Evolution requires the protected audit rubric in current and candidate content.")
    if current_path.read_bytes() != candidate_path.read_bytes():
        raise HarnessError("Evolution cannot modify or replace the protected audit rubric.")

def require_evolution_proposal(path: Path) -> None:
    if not path.is_file():
        raise HarnessError(f"Evolution proposal is missing: {path}")
    content = path.read_text(encoding="utf-8", errors="replace")
    has_title = any(re.match(r"^#{1,6}\s+\S", line.strip()) for line in content.splitlines())
    has_decision = bool(re.search(r"\b(?:promote|retain|merge|retire|archive-only)\b", content, re.IGNORECASE))
    if not has_title or not has_decision:
        raise HarnessError(
            "Evolution proposal requires a title and at least one Promote/Retain/Merge/Retire/Archive-only decision."
        )


def _local_evidence_sources(*values: Any) -> list[str]:
    sources: list[str] = []

    def walk(value: Any, field: str | None = None) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                walk(nested, key)
        elif isinstance(value, list):
            for nested in value:
                walk(nested, field)
        elif isinstance(value, str) and field == "evidence":
            normalized = value.strip().replace("\\", "/")
            if normalized and not normalized.startswith(("http://", "https://", "user:", "contract:", "registry:")):
                sources.append(normalized)

    for value in values:
        walk(value)
    return list(dict.fromkeys(sources))


def load_focused_evolution_bundle(bundle: Path) -> dict[str, Any]:
    delta = read_json(bundle / "creation-delta.json", None)
    if not isinstance(delta, dict):
        raise HarnessError("Focused Evolution bundle requires creation-delta.json.")
    if delta.get("schema_version") != SCHEMA_VERSION or delta.get("mode") != "evolution-focused":
        raise HarnessError(
            "Focused Evolution creation-delta.json requires schema_version 1.0 and mode evolution-focused."
        )
    decisions = delta.get("decisions", [])
    artifacts = delta.get("artifacts", [])
    if not isinstance(decisions, list) or not isinstance(artifacts, list) or not artifacts:
        raise HarnessError("Focused Evolution requires decision and artifact arrays plus at least one artifact mutation.")
    return delta


def load_evolution_bundle(
    args: argparse.Namespace,
    context: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any], dict[str, Any] | None, Path]:
    bundle = Path(args.analysis_bundle).expanduser().resolve()
    if not bundle.is_dir():
        raise HarnessError(f"Evolution bundle is not a directory: {bundle}")
    full_names = ("project-profile.json", "audit.json", "creation-delta.json", "architecture.json")
    if all((bundle / name).is_file() for name in full_names):
        profile, audit, delta, architecture, loaded = load_analysis_bundle(args, context)
        if loaded is None or profile.get("analysis_status") != "complete":
            raise HarnessError("Full Evolution staging requires a complete analysis bundle.")
        return "full", profile, audit, delta, architecture, loaded
    delta = load_focused_evolution_bundle(bundle)
    return "focused", None, None, delta, None, bundle


def verify_source_snapshot(context: dict[str, Any], metadata: dict[str, Any]) -> None:
    binding = metadata.get("source_snapshot", {})
    sources = binding.get("sources", []) if isinstance(binding, dict) else []
    expected = binding.get("digest") if isinstance(binding, dict) else None
    if not sources and not expected:
        return
    if not isinstance(sources, list) or not all(isinstance(source, str) for source in sources) or not expected:
        raise HarnessError("Staged Evolution candidate has invalid source snapshot metadata.")
    current = SourceFingerprintSnapshot(context)
    if current.digest(sources) != expected:
        raise HarnessError("Project evidence changed after Evolution candidate validation; restage the candidate.")


def verify_candidate_binding(
    candidate: Path,
    context: dict[str, Any],
    metadata: dict[str, Any],
    base_fingerprint: str,
) -> str:
    if metadata.get("binding_version") != "source-snapshot-v1":
        raise HarnessError("Staged Evolution candidate is missing its source-bound integrity metadata.")
    content_fingerprint = harness_content_fingerprint(candidate)
    if content_fingerprint != metadata.get("candidate_content_fingerprint"):
        raise HarnessError("Staged Evolution candidate was modified after validation.")
    source_binding = metadata.get("source_snapshot")
    source_digest = source_binding.get("digest") if isinstance(source_binding, dict) else None
    if not isinstance(source_digest, str) or candidate_binding_fingerprint(
        content_fingerprint, source_digest,
    ) != metadata.get("candidate_fingerprint"):
        raise HarnessError("Staged Evolution candidate metadata was modified after validation.")
    if content_fingerprint == base_fingerprint:
        raise HarnessError("keep requires a candidate that changes Harness content.")
    verify_source_snapshot(context, metadata)
    return content_fingerprint

@guard_project_skill
def evolve_stage(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    owner_id = canonical_id(args.owner, "Evolution owner id")
    owner = require_evolution_owner(skill_root, owner_id)
    proposal_id = canonical_id(args.proposal_id, "Evolution proposal id")
    proposal = skill_root / "state" / "evolution" / "proposals" / f"{proposal_id}.md"
    require_evolution_proposal(proposal)
    mode, profile, audit, delta, architecture, bundle = load_evolution_bundle(args, context)
    source_snapshot = SourceFingerprintSnapshot(context)
    source_snapshot.prime(_local_evidence_sources(profile, audit, delta, architecture))
    if mode == "full":
        current_knowledge = knowledge_check_internal(skill_root, context, source_snapshot)
        current_types = {
            canonical_knowledge_finding_type(item["type"])
            for item in [*current_knowledge.get("findings", []), *current_knowledge.get("warnings", [])]
        }
        classified_types = {
            canonical_knowledge_finding_type(item.get("type"))
            for item in (audit or {}).get("knowledge_findings", [])
        }
        missing_classifications = sorted(current_types - classified_types)
        if missing_classifications:
            raise HarnessError(
                "Evolution audit must classify every current knowledge finding before staging: "
                + ", ".join(missing_classifications)
            )
        entropy_types = {
            "duplicate_current_fact_candidates", "archive_ledger_leakage",
            "multiple_current_state_owners", "roadmap_current_state_conflict",
        }
        if current_types & entropy_types and not (audit or {}).get("entropy_report"):
            raise HarnessError("Evolution audit requires a before/after entropy_report for current entropy findings.")
    staging_root = skill_root / "state" / "evolution" / "staging"
    candidate = staging_root / proposal_id
    if candidate.exists():
        raise HarnessError(f"Evolution candidate already exists: {proposal_id}")
    staging_root.mkdir(parents=True, exist_ok=True)
    copy_non_state_skill(skill_root, candidate)
    (candidate / "state").mkdir(parents=True, exist_ok=True)
    atomic_write_json(candidate / "state" / "manifest.json", read_json(skill_root / "state" / "manifest.json", {}))
    try:
        if mode == "full":
            installed = install_analysis_bundle(
                candidate,
                context,
                profile or {},
                audit or {},
                delta,
                architecture or {},
                bundle,
                bool(getattr(args, "allow_executable_artifacts", False)),
                source_snapshot,
            )
        else:
            artifacts = apply_creation_delta(
                candidate,
                bundle,
                delta,
                context,
                bool(getattr(args, "allow_executable_artifacts", False)),
                allow_retire=True,
            )
            installed = {
                "knowledge": {"refreshed": False},
                "artifacts": artifacts,
                "rules": {"affected_only": True},
            }
        protect_audit_rubric(skill_root, candidate)
        check = knowledge_check_internal(
            candidate,
            context,
            source_snapshot,
            include_fingerprints=mode == "full",
        )
        if not check["healthy"]:
            raise HarnessError(f"Evolution candidate knowledge validation failed: {check['findings']}")
        bound_sources = source_snapshot.local_sources()
        source_digest = source_snapshot.digest(bound_sources)
        verification_snapshot = SourceFingerprintSnapshot(context)
        if verification_snapshot.digest(bound_sources) != source_digest:
            raise HarnessError("Project evidence changed while staging the Evolution candidate; retry staging.")
    except Exception:
        if candidate.exists():
            remove_owned_tree(candidate, staging_root, "Evolution candidate")
        raise
    candidate_content_fingerprint = harness_content_fingerprint(candidate)
    candidate_fingerprint = candidate_binding_fingerprint(candidate_content_fingerprint, source_digest)
    atomic_write_json(
        candidate / "state" / "candidate.json",
        {
            "schema_version": SCHEMA_VERSION,
            "proposal_id": proposal_id,
            "owner": owner.get("owner"),
            "base_fingerprint": owner.get("base_fingerprint"),
            "binding_version": "source-snapshot-v1",
            "candidate_content_fingerprint": candidate_content_fingerprint,
            "candidate_fingerprint": candidate_fingerprint,
            "mode": mode,
            "source_snapshot": {"sources": bound_sources, "digest": source_digest},
            "created_at": utc_now(),
        },
    )
    changed_paths = list(installed.get("artifacts", {}).get("applied", []))
    if "references/rules/red_lines.yaml" in changed_paths:
        changed_paths.extend(["references/rules/critical.md", "references/rules/by-stage"])
    if mode == "full":
        changed_paths.extend(["references/project_wiki", "state/analysis"])
    return {
        "status": "candidate_staged",
        "mode": mode,
        "proposal_id": proposal_id,
        "candidate": str(candidate),
        "base_fingerprint": owner.get("base_fingerprint"),
        "candidate_fingerprint": candidate_fingerprint,
        "source_snapshot_digest": source_digest,
        "changed_paths": list(dict.fromkeys(changed_paths)),
        "next_action": "independent_judge",
        **installed,
    }

@guard_project_skill
def evolve_check(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    result = evolve_check_internal(skill_root)
    if args.claim_owner:
        owner_id = canonical_id(args.claim_owner, "Evolution owner id")
        if not args.e1_confirmed:
            raise HarnessError("Claiming evolution ownership requires explicit --e1-confirmed.")
        if not result["pending"]:
            raise HarnessError("Evolution is not pending.")
        owner = skill_root / "state" / "registry" / "locks" / "evolution-owner"
        existing_owner = read_json(owner / "owner.json", {})
        if existing_owner:
            if existing_owner.get("owner") != owner_id:
                raise HarnessError("Another evolution owner is already active.")
            require_evolution_owner(skill_root, owner_id)
            result["owner"] = owner_id
            result["proposal_path"] = str(skill_root / "state" / "evolution" / "proposals")
            return result
        acquire_writer(skill_root, "evolution", owner_id)
        try:
            owner.mkdir()
        except FileExistsError as exc:
            release_writer(skill_root, "evolution", owner_id)
            raise HarnessError("Another evolution owner is already active.") from exc
        atomic_write_json(owner / "owner.json", {
            "owner": owner_id,
            "claimed_at": utc_now(),
            "base_fingerprint": harness_content_fingerprint(skill_root),
            "pending_change_ids": result["eligible_unevaluated"],
        })
        result["owner"] = owner_id
        result["proposal_path"] = str(skill_root / "state" / "evolution" / "proposals")
    return result

def evolution_judge_report(
    report_path: str,
    proposal_id: str,
    owner_id: str,
    candidate_fingerprint: str | None,
) -> dict[str, Any]:
    try:
        return validate_evolution_judge(
            report_path, proposal_id, owner_id, candidate_fingerprint, canonical_id,
        )
    except ValueError as exc:
        raise HarnessError(str(exc)) from exc

@guard_project_skill
def evolve_mark_complete(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    proposal_id = canonical_id(args.proposal_id, "Evolution proposal id")
    owner_id = canonical_id(args.owner, "Evolution owner id")
    with short_registry_lock(skill_root, "evolution-state"):
        state_path = skill_root / "state" / "evolution" / "state.json"
        pending_path = skill_root / "state" / "evolution" / "pending.json"
        results_path = skill_root / "state" / "evolution" / "results.tsv"
        manifest_path = skill_root / "state" / "manifest.json"
        state = read_json(state_path, {})
        pending_ids = state.get("pending_change_ids", [])
        current_owner = evolution_owner_record(skill_root)
        owner_is_current_window = bool(
            pending_ids and current_owner.get("pending_change_ids") == pending_ids
        )
        if state.get("last_proposal_id") == proposal_id and not owner_is_current_window:
            if state.get("last_owner_id") != owner_id:
                raise HarnessError("Completed Evolution owner does not match this retry.")
            owner_path = skill_root / "state" / "registry" / "locks" / "evolution-owner"
            owner = current_owner
            if owner and owner.get("owner") != owner_id:
                raise HarnessError("Evolution cleanup is owned by another E1 owner.")
            writer = read_json(writer_lock_path(skill_root) / "owner.json", {})
            if writer and (
                writer.get("kind") != "evolution" or writer.get("owner_id") != owner_id
            ):
                raise HarnessError("Evolution cleanup cannot release another operation's writer.")
            if owner_path.exists():
                remove_owned_tree(owner_path, owner_path.parent, "Evolution owner claim")
            if writer:
                release_writer(skill_root, "evolution", owner_id)
            staging = skill_root / "state" / "evolution" / "staging"
            if staging.exists():
                for staged_candidate in staging.iterdir():
                    if staged_candidate.is_dir() or staged_candidate.is_symlink():
                        remove_owned_tree(staged_candidate, staging, "Evolution staged candidate")
            next_window = evolve_check_locked(skill_root)
            return {
                "status": "already_completed",
                "result_status": state.get("last_result_status"),
                "evaluated_change_ids": state.get("last_evaluated_change_ids", []),
                "score": state.get("last_score"),
                "next_window": next_window,
            }
        if not pending_ids:
            raise HarnessError("No pending evolution window exists.")
        owner_path = skill_root / "state" / "registry" / "locks" / "evolution-owner"
        owner = require_evolution_owner(skill_root, owner_id)
        owner_pending = owner.get("pending_change_ids", [])
        if owner_pending != pending_ids:
            raise HarnessError("Evolution owner claim does not match the frozen pending Change window.")
        proposal = skill_root / "state" / "evolution" / "proposals" / f"{proposal_id}.md"
        require_evolution_proposal(proposal)
        base_fingerprint = owner.get("base_fingerprint")
        current_fingerprint = harness_content_fingerprint(skill_root)
        if current_fingerprint != base_fingerprint:
            raise HarnessError("Current Harness changed outside the staged Evolution candidate.")

        candidate: Path | None = None
        metadata: dict[str, Any] = {}
        candidate_id: str | None = None
        if args.status == "keep":
            if not args.candidate_id:
                raise HarnessError("A keep result requires --candidate-id for the validated staged candidate.")
            candidate_id = canonical_id(args.candidate_id, "Evolution candidate id")
            candidate = skill_root / "state" / "evolution" / "staging" / candidate_id
            metadata = read_json(candidate / "state" / "candidate.json", {})
            if metadata.get("proposal_id") != proposal_id or metadata.get("owner") != owner_id:
                raise HarnessError("Staged candidate does not match the proposal or evolution owner.")
            if metadata.get("base_fingerprint") != base_fingerprint:
                raise HarnessError("Staged candidate was built from a different Harness baseline.")
            protect_audit_rubric(skill_root, candidate)
            verify_candidate_binding(candidate, context, metadata, base_fingerprint)

        judge: dict[str, Any] | None = None
        if args.judge_report:
            judge = evolution_judge_report(
                args.judge_report,
                proposal_id,
                owner_id,
                metadata.get("candidate_fingerprint") if candidate is not None else None,
            )
            if judge["verdict"] != args.status:
                raise HarnessError("Evolution status does not match the judge report verdict.")
        elif not (args.status == "noop" and args.judge_unavailable):
            raise HarnessError("Evolution completion requires --judge-report, except unavailable judge noop.")
        validation = judge.get("validation", {}) if judge else {}
        gate = load_audit_rubric(skill_root)["evolution_gate"]
        passed = bool(
            judge
            and judge["score"] >= gate["minimum_score"]
            and (not gate["require_no_hard_issues"] or not judge["hard_issues"])
            and (not gate["require_harness_validation"] or validation.get("harness_passed"))
            and (not gate["require_project_validation"] or validation.get("project_passed"))
            and (
                not gate["require_full_test_when_declared"]
                or not validation.get("full_test_required")
                or validation.get("full_test_passed")
            )
            and (gate["allow_dry_run_keep"] or judge["eval_mode"] != "dry_run")
        )
        if args.status == "keep" and not passed:
            raise HarnessError(
                f"keep requires a bound score >= {gate['minimum_score']}, no hard issue, "
                "and passing validation."
            )
        score = judge.get("score") if judge else None
        eval_mode = judge.get("eval_mode") if judge else "unavailable"

        snapshots = capture_file_snapshots((state_path, pending_path, results_path, manifest_path))
        transaction: dict[str, Any] | None = None
        try:
            if candidate is not None and candidate_id is not None:
                verify_candidate_binding(candidate, context, metadata, base_fingerprint)
                recover_content_transactions(skill_root, "evolution", candidate_id)
                transaction = apply_content_transaction(
                    skill_root,
                    candidate,
                    "evolution",
                    candidate_id,
                    state_snapshot_paths=(state_path, pending_path, results_path, manifest_path),
                )
                if harness_content_fingerprint(skill_root) != metadata.get("candidate_content_fingerprint"):
                    raise HarnessError("Published candidate fingerprint does not match the validated candidate.")
            atomic_append_tsv(
                results_path,
                [
                    utc_now(), proposal_id, ",".join(pending_ids),
                    "" if score is None else str(score), args.status,
                    eval_mode, args.note or "",
                ],
            )
            state["evaluated_change_ids"] = list(dict.fromkeys([
                *state.get("evaluated_change_ids", []), *pending_ids,
            ]))
            state["pending_change_ids"] = []
            state["pending"] = False
            state["last_completed_at"] = utc_now()
            state["last_proposal_id"] = proposal_id
            state["last_owner_id"] = owner_id
            state["last_result_status"] = args.status
            state["last_score"] = score
            state["last_judge_report"] = judge
            state["last_evaluated_change_ids"] = list(pending_ids)
            atomic_write_json(state_path, state)
            pending_path.unlink(missing_ok=True)
            if args.status == "keep":
                manifest = read_json(manifest_path, {})
                manifest["skill_revision"] = int(manifest.get("skill_revision", 1)) + 1
                manifest["updated_at"] = utc_now()
                atomic_write_json(manifest_path, manifest)
        except Exception:
            if transaction is not None:
                rollback_content_transaction(transaction)
            restore_file_snapshots(snapshots)
            raise
        if transaction is not None:
            commit_content_transaction(transaction)
        if owner_path.exists():
            remove_owned_tree(owner_path, owner_path.parent, "Evolution owner claim")
        release_writer(skill_root, "evolution", owner_id)
        staging = skill_root / "state" / "evolution" / "staging"
        if staging.exists():
            for staged_candidate in staging.iterdir():
                if staged_candidate.is_dir() or staged_candidate.is_symlink():
                    remove_owned_tree(staged_candidate, staging, "Evolution staged candidate")
        next_window = evolve_check_locked(skill_root)
        return {
            "status": args.status,
            "evaluated_change_ids": pending_ids,
            "score": score,
            "next_window": next_window,
        }
