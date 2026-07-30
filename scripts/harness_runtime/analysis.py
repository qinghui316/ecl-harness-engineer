"""Evidence and four-file analysis-bundle validation."""

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

from .contracts import reject_secret_values, validate_architecture, validate_audit
from .core import HarnessError, SCHEMA_VERSION, is_within, read_json, safe_relative, slugify
from .project import primary_worktree_root

DISPLAY_TEXT_FIELDS = ("name", "summary", "rule", "title", "path", "id")

def semantic_display_text(item: Any, fields: tuple[str, ...] = DISPLAY_TEXT_FIELDS) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for field in fields:
            value = item.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""

def evidence_values(item: dict[str, Any]) -> list[str]:
    values = item.get("evidence", [])
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(value, str) and value.strip() for value in values)
    ):
        raise HarnessError("Evidence must be a non-empty string array.")
    return list(dict.fromkeys(value.strip().replace("\\", "/") for value in values))

def validate_project_evidence(root: Path, values: list[str], label: str) -> None:
    for value in values:
        if value.startswith(("http://", "https://", "user:", "contract:", "registry:")):
            continue
        relative = safe_relative(value, label)
        evidence_path = root / relative
        if not evidence_path.exists():
            raise HarnessError(f"{label} evidence does not exist: {relative}")
        if not is_within(evidence_path.resolve(), root):
            raise HarnessError(f"{label} evidence resolves outside the project: {relative}")

def reference_checkout(root: Path, reference: dict[str, Any]) -> tuple[str, Path]:
    reference_id = reference.get("id")
    checkout = safe_relative(str(reference.get("checkout", "")), f"reference project {reference_id} checkout")
    allowed_roots = (
        f".agents/reference-projects/{reference_id}",
        f"reference-projects/{reference_id}",
    )
    if checkout not in allowed_roots:
        raise HarnessError(
            f"Reference project {reference_id} checkout must be project-local at one of: "
            + ", ".join(allowed_roots)
        )
    path = root / checkout
    if not path.is_dir() or not is_within(path.resolve(), root):
        raise HarnessError(f"Reference project {reference_id} checkout is missing or escapes the project: {checkout}")
    return checkout, path

def validate_reference_evidence(
    root: Path,
    reference: dict[str, Any],
    values: list[str],
    label: str,
) -> None:
    _, checkout = reference_checkout(root, reference)
    for value in values:
        relative = safe_relative(value, label)
        evidence_path = checkout / relative
        if not evidence_path.exists():
            raise HarnessError(f"{label} evidence does not exist in the reference checkout: {relative}")
        if not is_within(evidence_path.resolve(), checkout):
            raise HarnessError(f"{label} evidence resolves outside the reference checkout: {relative}")

def reference_project_sources(
    root: Path,
    reference: dict[str, Any],
    values: list[str],
) -> list[str]:
    checkout, _ = reference_checkout(root, reference)
    return [(Path(checkout) / safe_relative(value, "reference evidence")).as_posix() for value in values]

def bootstrap_profile(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_status": "bootstrap_only",
        "project_id": context["project_id"],
        "project_name": context["project_name"],
        "purpose": None,
        "primary_flows": [],
        "languages": [],
        "frameworks": [],
        "package_managers": [],
        "source_roots": [],
        "entrypoints": [],
        "modules": [],
        "commands": [],
        "environment": {
            "services": [], "variables": [], "modes": [], "startup_order": [],
            "helpers": [], "unknowns": [], "evidence": [],
        },
        "documents": [],
        "ci": [],
        "bridges": [],
        "reference_projects": [],
        "global_boundaries": [],
        "unknowns": [
            "Project purpose, module boundaries, commands, environment, and semantic bridges have not been analyzed."
        ],
        "evidence": [],
    }

def validate_profile(profile: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict) or profile.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError("project-profile.json must use schema_version 1.0.")
    if profile.get("project_id") not in (None, context["project_id"]):
        raise HarnessError("Project profile id does not match the target project.")
    profile["project_id"] = context["project_id"]
    profile.setdefault("project_name", context["project_name"])
    if profile.get("analysis_status") not in {"complete", "partial", "bootstrap_only"}:
        raise HarnessError("Project profile must declare complete, partial, or bootstrap_only analysis_status.")
    try:
        reject_secret_values(profile)
    except ValueError as exc:
        raise HarnessError(str(exc)) from exc
    for key in (
        "primary_flows", "languages", "frameworks", "package_managers", "source_roots",
        "entrypoints", "modules", "commands", "documents", "ci", "bridges", "reference_projects",
        "global_boundaries", "unknowns", "evidence",
    ):
        if not isinstance(profile.setdefault(key, []), list):
            raise HarnessError(f"Project profile field {key} must be an array.")
    root: Path = context["project_root"]
    reference_root = primary_worktree_root(context)
    purpose = profile.get("purpose")
    if purpose is not None:
        if (
            not isinstance(purpose, dict)
            or not isinstance(purpose.get("summary"), str)
            or not purpose["summary"].strip()
        ):
            raise HarnessError("Project purpose must contain a summary and evidence.")
        validate_project_evidence(root, evidence_values(purpose), "purpose")
    if profile.get("analysis_status") == "complete":
        if purpose is None:
            raise HarnessError(
                "A complete project profile requires an evidence-backed purpose; use bootstrap_only when project semantics are unknown."
            )
        validate_project_evidence(root, evidence_values(profile), "profile")
        implementation_fields = ("source_roots", "entrypoints", "modules")
        project_use_fields = ("primary_flows", "commands", "documents", "ci", "global_boundaries")
        if not profile["languages"] or not any(profile[field] for field in implementation_fields):
            raise HarnessError(
                "A complete project profile requires evidence-backed language and implementation structure."
            )
        if not any(profile[field] for field in project_use_fields):
            raise HarnessError(
                "A complete project profile requires evidence-backed workflow, command, document, CI, or boundary facts."
            )
        for field in (
            "primary_flows", "languages", "frameworks", "package_managers", "source_roots",
            "entrypoints", "documents", "ci", "global_boundaries",
        ):
            for item in profile[field]:
                if not isinstance(item, dict):
                    raise HarnessError(f"Complete profile field {field} must contain evidence-backed objects.")
                display_fields = {
                    "primary_flows": ("name", "summary", "title", "id"),
                    "documents": ("name", "title", "path", "id"),
                    "ci": ("name", "title", "path", "id"),
                    "global_boundaries": ("rule", "name", "summary"),
                }
                if field in display_fields and not semantic_display_text(item, display_fields[field]):
                    raise HarnessError(
                        f"Complete profile field {field} contains an item with no displayable semantic text."
                    )
                validate_project_evidence(root, evidence_values(item), f"profile {field}")
    references_by_id: dict[str, dict[str, Any]] = {}
    for reference in profile["reference_projects"]:
        if not isinstance(reference, dict):
            raise HarnessError("Each reference project must be an object.")
        reference_id = reference.get("id")
        if (
            not isinstance(reference_id, str)
            or slugify(reference_id) != reference_id
            or reference_id in references_by_id
        ):
            raise HarnessError(f"Invalid or duplicate reference project id: {reference_id!r}")
        for field in ("name", "source", "inspected_commit", "purpose"):
            if not isinstance(reference.get(field), str) or not reference[field].strip():
                raise HarnessError(f"Reference project {reference_id} requires {field}.")
        if reference.get("global_relevance") is not None and (
            not isinstance(reference["global_relevance"], str) or not reference["global_relevance"].strip()
        ):
            raise HarnessError(f"Reference project {reference_id} global_relevance must be a non-empty string.")
        for field in ("applicable_problems", "inspected_files", "modules", "unknowns"):
            if not isinstance(reference.setdefault(field, []), list):
                raise HarnessError(f"Reference project {reference_id} field {field} must be an array.")
        if not all(isinstance(item, str) and item.strip() for item in reference["applicable_problems"]):
            raise HarnessError(f"Reference project {reference_id} applicable_problems must contain strings.")
        if not all(isinstance(item, str) and item.strip() for item in reference["unknowns"]):
            raise HarnessError(f"Reference project {reference_id} unknowns must contain strings.")
        reference_checkout(reference_root, reference)
        validate_reference_evidence(
            reference_root, reference, evidence_values(reference), f"reference project {reference_id}"
        )
        for inspected in reference["inspected_files"]:
            if not isinstance(inspected, dict) or not all(
                isinstance(inspected.get(field), str) and inspected[field].strip()
                for field in ("path", "reason")
            ):
                raise HarnessError(f"Reference project {reference_id} inspected_files require path and reason.")
            validate_reference_evidence(
                reference_root, reference, [inspected["path"]],
                f"reference project {reference_id} inspected file",
            )
        reference_module_ids: set[str] = set()
        for reference_module in reference["modules"]:
            if not isinstance(reference_module, dict):
                raise HarnessError(f"Reference project {reference_id} modules must contain objects.")
            reference_module_id = reference_module.get("id")
            if (
                not isinstance(reference_module_id, str)
                or slugify(reference_module_id) != reference_module_id
                or reference_module_id in reference_module_ids
            ):
                raise HarnessError(
                    f"Reference project {reference_id} has invalid or duplicate module id: {reference_module_id!r}"
                )
            reference_module_ids.add(reference_module_id)
            for field in ("name", "responsibility"):
                if not isinstance(reference_module.get(field), str) or not reference_module[field].strip():
                    raise HarnessError(
                        f"Reference project {reference_id} module {reference_module_id} requires {field}."
                    )
            for field in ("roots", "entrypoints", "interfaces", "call_paths", "tests"):
                if not isinstance(reference_module.setdefault(field, []), list):
                    raise HarnessError(
                        f"Reference project {reference_id} module {reference_module_id} field {field} must be an array."
                    )
            validate_reference_evidence(
                reference_root, reference, evidence_values(reference_module),
                f"reference project {reference_id} module {reference_module_id}",
            )
        references_by_id[reference_id] = reference

    module_ids: set[str] = set()
    for module in profile["modules"]:
        if not isinstance(module, dict):
            raise HarnessError("Each module must be an object.")
        module_id = module.get("id")
        if not isinstance(module_id, str) or slugify(module_id) != module_id or module_id in module_ids:
            raise HarnessError(f"Invalid or duplicate module id: {module_id!r}")
        module_ids.add(module_id)
        if not isinstance(module.get("name"), str) or not isinstance(module.get("responsibility"), str):
            raise HarnessError(f"Module {module_id} requires name and responsibility.")
        for field in ("roots", "entrypoints", "interfaces", "dependencies", "tests", "commands", "boundaries"):
            if not isinstance(module.setdefault(field, []), list):
                raise HarnessError(f"Module {module_id} field {field} must be an array.")
        validate_project_evidence(root, evidence_values(module), f"module {module_id}")
        relations = module.setdefault("reference_sources", [])
        if not isinstance(relations, list):
            raise HarnessError(f"Module {module_id} reference_sources must be an array.")
        for relation in relations:
            if not isinstance(relation, dict):
                raise HarnessError(f"Module {module_id} reference_sources must contain objects.")
            reference_id = relation.get("reference_id")
            reference = references_by_id.get(reference_id)
            if reference is None:
                raise HarnessError(f"Module {module_id} names unknown reference project: {reference_id!r}")
            for field in ("mechanism", "adaptation", "validation"):
                if not isinstance(relation.get(field), str) or not relation[field].strip():
                    raise HarnessError(f"Module {module_id} reference {reference_id} requires {field}.")
            if not isinstance(relation.setdefault("boundaries", []), list):
                raise HarnessError(f"Module {module_id} reference {reference_id} boundaries must be an array.")
            if not all(isinstance(item, str) and item.strip() for item in relation["boundaries"]):
                raise HarnessError(f"Module {module_id} reference {reference_id} boundaries must contain strings.")
            target_evidence = relation.get("target_evidence")
            reference_evidence = relation.get("reference_evidence")
            if not isinstance(target_evidence, list) or not target_evidence:
                raise HarnessError(f"Module {module_id} reference {reference_id} requires target_evidence.")
            if not isinstance(reference_evidence, list) or not reference_evidence:
                raise HarnessError(f"Module {module_id} reference {reference_id} requires reference_evidence.")
            validate_project_evidence(root, target_evidence, f"module {module_id} reference target")
            validate_reference_evidence(
                reference_root, reference, reference_evidence, f"module {module_id} reference source"
            )
    bridge_ids: set[str] = set()
    for bridge in profile["bridges"]:
        if not isinstance(bridge, dict):
            raise HarnessError("Each bridge must be an object.")
        bridge_id = bridge.get("id")
        if not isinstance(bridge_id, str) or slugify(bridge_id) != bridge_id or bridge_id in bridge_ids:
            raise HarnessError(f"Invalid or duplicate bridge id: {bridge_id!r}")
        bridge_ids.add(bridge_id)
        mappings = bridge.get("mappings")
        if not isinstance(mappings, list) or not mappings:
            raise HarnessError(f"Bridge {bridge_id} must contain evidence-backed mappings.")
        for mapping in mappings:
            if not isinstance(mapping, dict) or not mapping.get("from") or not mapping.get("to"):
                raise HarnessError(f"Bridge {bridge_id} has an invalid mapping.")
            validate_project_evidence(root, evidence_values(mapping), f"bridge {bridge_id}")
            reference_id = mapping.get("reference_id")
            if reference_id is not None:
                reference = references_by_id.get(reference_id)
                if reference is None:
                    raise HarnessError(f"Bridge {bridge_id} names unknown reference project: {reference_id!r}")
                reference_evidence = mapping.get("reference_evidence")
                if not isinstance(reference_evidence, list) or not reference_evidence:
                    raise HarnessError(f"Bridge {bridge_id} reference mapping requires reference_evidence.")
                validate_reference_evidence(
                    reference_root, reference, reference_evidence,
                    f"bridge {bridge_id} reference source",
                )
    for command in profile["commands"]:
        if not isinstance(command, dict) or not command.get("purpose") or not command.get("command"):
            raise HarnessError("Each command requires purpose and command.")
        if command.get("status") not in {"configured", "candidate", "executed"}:
            raise HarnessError("Command status must be configured, candidate, or executed.")
        validate_project_evidence(root, evidence_values(command), f"command {command.get('purpose')}")
    environment = profile.setdefault("environment", {"services": [], "variables": [], "modes": []})
    if not isinstance(environment, dict):
        raise HarnessError("Project environment must be an object.")
    for key in ("services", "variables", "modes", "startup_order", "helpers", "unknowns"):
        if not isinstance(environment.setdefault(key, []), list):
            raise HarnessError(f"Environment field {key} must be an array.")
        if profile.get("analysis_status") == "complete" and key in {"services", "variables", "modes", "helpers"}:
            for item in environment[key]:
                if not isinstance(item, dict):
                    raise HarnessError(f"Complete environment field {key} must contain evidence-backed objects.")
                environment_display_fields = {
                    "modes": ("name", "summary", "title", "id"),
                    "helpers": ("name", "summary", "title", "path", "id"),
                }
                if key in environment_display_fields and not semantic_display_text(
                    item, environment_display_fields[key]
                ):
                    raise HarnessError(
                        f"Complete environment field {key} contains an item with no displayable semantic text."
                    )
                validate_project_evidence(root, evidence_values(item), f"environment {key}")
    if not all(isinstance(item, (str, dict)) for item in environment["startup_order"]):
        raise HarnessError("Environment startup_order entries must be strings or evidence-backed objects.")
    for item in environment["startup_order"]:
        if isinstance(item, str):
            if not item.strip():
                raise HarnessError("Environment startup_order strings must not be empty.")
            continue
        if not semantic_display_text(item, (*DISPLAY_TEXT_FIELDS, "service", "step")):
            raise HarnessError("Environment startup_order object has no displayable semantic text.")
        if profile.get("analysis_status") == "complete":
            validate_project_evidence(root, evidence_values(item), "environment startup_order")
    if not all(isinstance(item, str) and item.strip() for item in environment["unknowns"]):
        raise HarnessError("Environment unknowns must be non-empty strings.")
    if environment.get("evidence"):
        validate_project_evidence(root, evidence_values(environment), "environment")
    for service in environment["services"]:
        if not isinstance(service.get("name"), str) or not service["name"].strip():
            raise HarnessError("Every environment service requires a name.")
        readiness = service.get("readiness")
        if readiness is not None:
            if not isinstance(readiness, dict) or readiness.get("type") not in {"http", "tcp", "log", "process", "none"}:
                raise HarnessError(f"Service {service['name']} has an invalid readiness contract.")
    for variable in environment["variables"]:
        if not isinstance(variable.get("name"), str) or not variable["name"].strip():
            raise HarnessError("Every environment variable requires a name.")
        if "sensitive" in variable and not isinstance(variable["sensitive"], bool):
            raise HarnessError(f"Environment variable {variable['name']} sensitive must be boolean.")
    return profile

def load_analysis_bundle(
    args: argparse.Namespace,
    context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], Path | None]:
    requested = getattr(args, "analysis_bundle", None)
    if not requested:
        return bootstrap_profile(context), {
            "schema_version": SCHEMA_VERSION,
            "analysis_status": "bootstrap_only",
            "gaps": [{
                "priority": "P1",
                "dimension": "project_knowledge",
                "issue": "Semantic project audit has not run.",
                "fix": "Analyze project evidence and supply a complete four-file bundle.",
                "evidence": [],
            }],
            "strengths": [],
        }, {
            "schema_version": SCHEMA_VERSION,
            "mode": "bootstrap",
            "decisions": [],
            "artifacts": [],
        }, {
            "schema_version": SCHEMA_VERSION,
            "analysis_status": "bootstrap_only",
            "layers": [],
            "circular_dependencies": [],
            "key_interfaces": [],
            "code_paths": [],
            "error_patterns": {},
            "evidence": [],
        }, None
    bundle = Path(requested).expanduser().resolve()
    if not bundle.is_dir():
        raise HarnessError(f"Analysis bundle is not a directory: {bundle}")
    names = ("project-profile.json", "audit.json", "creation-delta.json", "architecture.json")
    values = [read_json(bundle / name) for name in names]
    if any(not isinstance(value, dict) for value in values):
        raise HarnessError("Analysis bundle must contain project-profile.json, audit.json, creation-delta.json, and architecture.json.")
    profile = validate_profile(values[0], context)
    audit, delta, architecture = values[1], values[2], values[3]
    try:
        validate_audit(audit)
        validate_architecture(
            architecture,
            lambda evidence, label: validate_project_evidence(context["project_root"], evidence, label),
        )
    except ValueError as exc:
        raise HarnessError(str(exc)) from exc
    if profile.get("analysis_status") == "complete":
        if audit.get("analysis_status") != "complete":
            raise HarnessError("A complete project profile requires a complete audit.")
        if architecture.get("analysis_status") != "complete":
            raise HarnessError("A complete project profile requires a complete architecture analysis.")
    if delta.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError("Creation delta must use schema_version 1.0.")
    if not isinstance(delta.setdefault("decisions", []), list) or not isinstance(delta.setdefault("artifacts", []), list):
        raise HarnessError("Creation delta decisions and artifacts must be arrays.")
    if "capability_profiles" in delta:
        raise HarnessError(
            "Creation delta capability_profiles is obsolete. Declare evidence-backed project Harness artifacts directly."
        )
    for decision in delta["decisions"]:
        if not isinstance(decision, dict):
            raise HarnessError("Each creation-delta decision must be an object.")
        for field in ("source", "action", "owner", "projection", "validation"):
            if not isinstance(decision.get(field), str) or not decision[field].strip():
                raise HarnessError(f"Creation-delta decision requires {field}.")
        if decision["action"] not in {"retain", "move", "merge", "retire", "archive-only", "create"}:
            raise HarnessError(f"Invalid migration decision action: {decision['action']}")
    return profile, audit, delta, architecture, bundle
