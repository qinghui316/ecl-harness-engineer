#!/usr/bin/env python3
"""Public command facade for the project-bound local Harness Skill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_ROOT = Path(__file__).resolve().parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from harness_runtime.core import HarnessError
from harness_runtime.links import scaffold_runtime_available
from harness_runtime.project_commands import project_audit, project_doctor, project_init, project_migrate
from harness_runtime.changes import (
    change_close, change_context, change_new, change_park, change_preflight, change_publish,
    change_reindex, change_resume, change_search, change_status,
)
from harness_runtime.integration import integrate_abort, integrate_complete, integrate_start, integrate_status
from harness_runtime.evolution import evolve_check, evolve_mark_complete, evolve_stage, evolve_status
from harness_runtime.knowledge import knowledge_check, knowledge_scan

def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", default=".")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project-bound local Harness Skill commands")
    domains = parser.add_subparsers(dest="domain", required=True)

    project = domains.add_parser("project")
    project_actions = project.add_subparsers(dest="action", required=True)
    project_commands = ["audit", "doctor"]
    if scaffold_runtime_available():
        project_commands = ["init", "audit", "migrate", "doctor"]
    for action in project_commands:
        command = project_actions.add_parser(action)
        add_common(command)
        if action in {"init", "migrate"}:
            command.add_argument("--analysis-bundle")
            command.add_argument("--canonical-branch")
        elif action == "audit":
            command.add_argument("--analysis-bundle")
        if action in {"init", "migrate"}:
            command.add_argument("--allow-executable-artifacts", action="store_true")
        if action == "doctor":
            command.add_argument("--stale-after-hours", type=int, default=168)
            command.add_argument("--repair-links", action="store_true")

    change = domains.add_parser("change")
    change_actions = change.add_subparsers(dest="action", required=True)
    new = change_actions.add_parser("new")
    add_common(new)
    new.add_argument("change_id")
    new.add_argument("--scope")
    preflight = change_actions.add_parser("preflight")
    add_common(preflight)
    preflight.add_argument("--change-id")
    publish = change_actions.add_parser("publish")
    add_common(publish)
    publish.add_argument("change_id")
    publish.add_argument("--scope")
    publish.add_argument("--paths", nargs="*")
    publish.add_argument("--status", choices=["planning", "active"])
    publish.add_argument("--validation", action="append")
    publish.add_argument("--contract")
    close = change_actions.add_parser("close")
    add_common(close)
    close.add_argument("change_id")
    close.add_argument("--status", required=True, choices=["completed", "blocked", "abandoned"])
    close.add_argument("--completion-commit")
    close.add_argument("--validation", action="append")
    close.add_argument("--validation-passed", action="store_true")
    park = change_actions.add_parser("park")
    add_common(park)
    park.add_argument("change_id")
    resume = change_actions.add_parser("resume")
    add_common(resume)
    resume.add_argument("change_id")
    search = change_actions.add_parser("search")
    add_common(search)
    search.add_argument("--query")
    search.add_argument("--status", action="append", choices=[
        "planning", "active", "parking", "completed", "blocked", "abandoned",
    ])
    context = change_actions.add_parser("context")
    add_common(context)
    context.add_argument("change_id")
    context.add_argument("--full", action="store_true")
    reindex = change_actions.add_parser("reindex")
    add_common(reindex)
    status = change_actions.add_parser("status")
    add_common(status)
    status.add_argument("--change-id")

    integrate = domains.add_parser("integrate")
    integrate_actions = integrate.add_subparsers(dest="action", required=True)
    start = integrate_actions.add_parser("start")
    add_common(start)
    start.add_argument("integration_id")
    start.add_argument("change_ids", nargs="+")
    start.add_argument("--completion-commit", action="append", default=[])
    integration_status = integrate_actions.add_parser("status")
    add_common(integration_status)
    integration_status.add_argument("--integration-id")
    integration_status.add_argument("--resume", action="store_true")
    complete = integrate_actions.add_parser("complete")
    add_common(complete)
    complete.add_argument("integration_id")
    complete.add_argument("--confirm-i2", action="store_true")
    complete.add_argument("--validation", action="append")
    complete.add_argument("--validation-passed", action="store_true")
    complete.add_argument("--review-report")
    abort = integrate_actions.add_parser("abort")
    add_common(abort)
    abort.add_argument("integration_id")

    evolve = domains.add_parser("evolve")
    evolve_actions = evolve.add_subparsers(dest="action", required=True)
    check = evolve_actions.add_parser("check")
    add_common(check)
    check.add_argument("--claim-owner")
    check.add_argument("--e1-confirmed", action="store_true")
    evolve_status_parser = evolve_actions.add_parser("status")
    add_common(evolve_status_parser)
    stage = evolve_actions.add_parser("stage")
    add_common(stage)
    stage.add_argument("--proposal-id", required=True)
    stage.add_argument("--owner", required=True)
    stage.add_argument("--analysis-bundle", required=True)
    stage.add_argument("--allow-executable-artifacts", action="store_true")
    mark = evolve_actions.add_parser("mark-complete")
    add_common(mark)
    mark.add_argument("--proposal-id", required=True)
    mark.add_argument("--owner", required=True)
    mark.add_argument("--candidate-id")
    mark.add_argument("--judge-report")
    mark.add_argument("--judge-unavailable", action="store_true")
    mark.add_argument("--status", required=True, choices=["keep", "rejected", "noop"])
    mark.add_argument("--note")

    knowledge = domains.add_parser("knowledge")
    knowledge_actions = knowledge.add_subparsers(dest="action", required=True)
    for action in ("scan", "check"):
        command = knowledge_actions.add_parser(action)
        add_common(command)

    return parser

def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    handlers = {
        ("project", "init"): project_init,
        ("project", "audit"): project_audit,
        ("project", "migrate"): project_migrate,
        ("project", "doctor"): project_doctor,
        ("change", "new"): change_new,
        ("change", "preflight"): change_preflight,
        ("change", "publish"): change_publish,
        ("change", "close"): change_close,
        ("change", "park"): change_park,
        ("change", "resume"): change_resume,
        ("change", "search"): change_search,
        ("change", "context"): change_context,
        ("change", "reindex"): change_reindex,
        ("change", "status"): change_status,
        ("integrate", "start"): integrate_start,
        ("integrate", "status"): integrate_status,
        ("integrate", "complete"): integrate_complete,
        ("integrate", "abort"): integrate_abort,
        ("evolve", "check"): evolve_check,
        ("evolve", "status"): evolve_status,
        ("evolve", "stage"): evolve_stage,
        ("evolve", "mark-complete"): evolve_mark_complete,
        ("knowledge", "scan"): knowledge_scan,
        ("knowledge", "check"): knowledge_check,
    }
    return handlers[(args.domain, args.action)](args)

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
    except (HarnessError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    if args.domain == "project" and args.action == "doctor" and not result.get("healthy", False):
        return 1
    if args.domain == "knowledge" and not result.get("healthy", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
