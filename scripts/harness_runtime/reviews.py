from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .contracts import load_bound_report


def validate_integration_review(
    report_path: str,
    record: dict[str, Any],
    candidate_commit: str,
    canonicalize: Callable[[str, str], str],
) -> dict[str, Any]:
    report = load_bound_report(Path(report_path).expanduser().resolve(), "Integration review")
    required = ("integration_id", "reviewer_id", "reviewed_commit", "verdict", "validation_commands", "findings")
    if not all(field in report for field in required):
        raise ValueError("Integration review report is missing required binding fields.")
    if report["integration_id"] != record["integration_id"] or report["reviewed_commit"] != candidate_commit:
        raise ValueError("Integration review report does not bind the current Integration candidate.")
    reviewer_id = canonicalize(report["reviewer_id"], "Integration reviewer id")
    if reviewer_id == record.get("integrator_id"):
        raise ValueError("Integration reviewer must differ from the recorded Integrator.")
    if report["verdict"] != "approved":
        raise ValueError("I2 requires an approved independent Integration review report.")
    if not isinstance(report["validation_commands"], list) or not report["validation_commands"]:
        raise ValueError("Integration review report requires validation command evidence.")
    if not all(isinstance(item, str) and item.strip() for item in report["validation_commands"]):
        raise ValueError("Integration review validation commands must be non-empty strings.")
    if not isinstance(report["findings"], list):
        raise ValueError("Integration review findings must be an array.")
    report["reviewer_id"] = reviewer_id
    return report


def validate_evolution_judge(
    report_path: str,
    proposal_id: str,
    owner_id: str,
    candidate_fingerprint: str | None,
    canonicalize: Callable[[str, str], str],
) -> dict[str, Any]:
    report = load_bound_report(Path(report_path).expanduser().resolve(), "Evolution judge")
    required = (
        "proposal_id", "reviewer_id", "candidate_fingerprint", "score", "hard_issues",
        "eval_mode", "validation", "verdict",
    )
    if not all(field in report for field in required):
        raise ValueError("Evolution judge report is missing required binding fields.")
    if report["proposal_id"] != proposal_id:
        raise ValueError("Evolution judge report does not bind the current proposal.")
    reviewer_id = canonicalize(report["reviewer_id"], "Evolution reviewer id")
    if reviewer_id == owner_id:
        raise ValueError("Evolution reviewer must differ from the Evolution owner.")
    if report["candidate_fingerprint"] != candidate_fingerprint:
        raise ValueError("Evolution review report does not bind the staged candidate integrity digest.")
    if not isinstance(report["score"], (int, float)) or not 0 <= report["score"] <= 100:
        raise ValueError("Evolution judge score must be between 0 and 100.")
    if not isinstance(report["hard_issues"], list):
        raise ValueError("Evolution hard_issues must be an array.")
    if report["eval_mode"] not in {"independent_review", "full_test", "dry_run"}:
        raise ValueError("Evolution eval_mode is invalid.")
    validation = report["validation"]
    if not isinstance(validation, dict):
        raise ValueError("Evolution judge validation must be an object.")
    for field in ("harness_passed", "project_passed", "full_test_required", "full_test_passed"):
        if not isinstance(validation.get(field), bool):
            raise ValueError(f"Evolution judge validation requires boolean {field}.")
    report["reviewer_id"] = reviewer_id
    return report
