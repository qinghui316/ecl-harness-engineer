from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

SECRET_FIELD_RE = re.compile(
    r"(?:^|_)(?:value|secret|password|passwd|token|api_key|private_key|credential|connection_string)(?:$|_)",
    re.IGNORECASE,
)
CLARIFICATION_RE = re.compile(r"\[NEEDS CLARIFICATION\s*:", re.IGNORECASE)
TASK_RE = re.compile(r"^- \[(?P<done>[ xX])\]\s+(?P<task>T\d{3,})\b(?P<body>.*)$")
AC_RE = re.compile(r"\bAC-\d{3,}\b")
AC_DEFINITION_RE = re.compile(
    r"^\s*[-*]\s*(?P<id>AC-\d{3,})\s*:\s*(?P<value>.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def task_field_value(block: str, field: str) -> str | None:
    match = re.search(
        rf"(?:^|[;\n])\s*(?:[-*]\s*)?{field}\s*:\s*([^;\n]+)",
        block,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).strip()
    return None if not value or re.search(r"\bTBD\b", value, re.IGNORECASE) else value


def audit_rubric_path(skill_root: Path | None = None) -> Path:
    root = skill_root or Path(__file__).resolve().parents[2]
    return root / "references" / "audit-rubric.json"


def load_audit_rubric(skill_root: Path | None = None) -> dict[str, Any]:
    path = audit_rubric_path(skill_root)
    try:
        rubric = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid audit rubric {path}: {exc}") from exc
    if rubric.get("schema_version") != "1.0":
        raise ValueError("Audit rubric must use schema_version 1.0.")
    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        raise ValueError("Audit rubric must define weighted dimensions.")
    if any(
        not isinstance(name, str)
        or not name
        or not isinstance(weight, int)
        or weight <= 0
        for name, weight in dimensions.items()
    ) or sum(dimensions.values()) != 100:
        raise ValueError("Audit rubric dimension weights must be positive integers totaling 100.")
    score_range = rubric.get("score_range")
    if not isinstance(score_range, dict) or not all(
        isinstance(score_range.get(key), (int, float)) for key in ("minimum", "maximum")
    ) or score_range["minimum"] >= score_range["maximum"]:
        raise ValueError("Audit rubric score_range is invalid.")
    gate = rubric.get("evolution_gate")
    if not isinstance(gate, dict) or not isinstance(gate.get("minimum_score"), (int, float)):
        raise ValueError("Audit rubric evolution_gate is invalid.")
    return rubric


def reject_secret_values(value: Any, path: str = "profile") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if SECRET_FIELD_RE.search(str(key)) and nested not in (None, "", [], {}):
                raise ValueError(f"Secret-bearing field is not allowed at {path}.{key}; record only the variable name and classification.")
            reject_secret_values(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            reject_secret_values(nested, f"{path}[{index}]")


def validate_architecture(
    architecture: dict[str, Any],
    validate_evidence: Callable[[list[str], str], None],
) -> dict[str, Any]:
    if architecture.get("schema_version") != "1.0":
        raise ValueError("architecture.json must use schema_version 1.0.")
    status = architecture.get("analysis_status")
    if status not in {"complete", "partial", "bootstrap_only"}:
        raise ValueError("Architecture must declare complete, partial, or bootstrap_only analysis_status.")
    for key in ("layers", "dependencies", "components", "circular_dependencies", "key_interfaces", "code_paths"):
        if not isinstance(architecture.setdefault(key, []), list):
            raise ValueError(f"Architecture field {key} must be an array.")
    if not isinstance(architecture.setdefault("error_patterns", {}), dict):
        raise ValueError("Architecture error_patterns must be an object.")
    if not isinstance(architecture.setdefault("evidence", []), list):
        raise ValueError("Architecture evidence must be an array.")
    if status == "complete":
        if not architecture["evidence"]:
            raise ValueError("A complete architecture requires project evidence.")
        if not any(architecture[key] for key in ("layers", "dependencies", "components", "key_interfaces", "code_paths")):
            raise ValueError("A complete architecture requires an evidenced layer, interface, or code path.")
    if architecture["evidence"]:
        validate_evidence(architecture["evidence"], "architecture")
    for key in ("layers", "dependencies", "components", "circular_dependencies", "key_interfaces", "code_paths"):
        for index, item in enumerate(architecture[key]):
            if not isinstance(item, dict):
                raise ValueError(f"Architecture field {key} must contain objects.")
            evidence = item.get("evidence", [])
            if status == "complete" and not evidence:
                raise ValueError(f"Complete architecture {key}[{index}] requires evidence.")
            if evidence:
                validate_evidence(evidence, f"architecture {key}[{index}]")
            if key == "dependencies" and not all(str(item.get(field, "")).strip() for field in ("from", "to")):
                raise ValueError(f"Architecture dependencies[{index}] requires from and to.")
            if key == "layers" and (
                "level" not in item
                or not isinstance(item.get("packages"), list)
                or not item["packages"]
            ):
                raise ValueError(f"Architecture layers[{index}] requires level and packages.")
            if key == "components" and not any(
                str(item.get(field, "")).strip() for field in ("name", "summary", "title", "path", "id")
            ):
                raise ValueError(f"Architecture components[{index}] requires displayable semantic text.")
            if key == "circular_dependencies" and not all(
                str(item.get(field, "")).strip() for field in ("pkg_a", "pkg_b")
            ):
                raise ValueError(f"Architecture circular_dependencies[{index}] requires pkg_a and pkg_b.")
            if key == "key_interfaces":
                if not str(item.get("name", "")).strip():
                    raise ValueError(f"Architecture key_interfaces[{index}] requires name.")
                if not isinstance(item.setdefault("implementations", []), list):
                    raise ValueError(f"Architecture key_interfaces[{index}].implementations must be an array.")
            if key == "code_paths":
                if not str(item.get("name", "")).strip():
                    raise ValueError(f"Architecture code_paths[{index}] requires name.")
                if not isinstance(item.get("flow", []), list):
                    raise ValueError(f"Architecture code_paths[{index}].flow must be an array.")
    return architecture


def validate_audit(audit: dict[str, Any]) -> dict[str, Any]:
    if audit.get("schema_version") != "1.0":
        raise ValueError("audit.json must use schema_version 1.0.")
    if audit.get("analysis_status") not in {"complete", "partial", "bootstrap_only"}:
        raise ValueError("Audit must declare complete, partial, or bootstrap_only analysis_status.")
    if "profile" in audit:
        raise ValueError("Audit profile is obsolete; score the single project Harness contract.")
    dimensions = audit.setdefault("dimensions", {})
    if audit["analysis_status"] == "complete":
        rubric = load_audit_rubric()
        audit_weights = rubric["dimensions"]
        score_range = rubric["score_range"]
        if set(dimensions) != set(audit_weights):
            raise ValueError("A complete audit must score every core audit dimension exactly once.")
        weighted = 0.0
        for name, expected_weight in audit_weights.items():
            item = dimensions[name]
            if not isinstance(item, dict):
                raise ValueError(f"Audit dimension {name} must be an object.")
            score = item.get("score")
            if (
                not isinstance(score, (int, float))
                or not score_range["minimum"] <= score <= score_range["maximum"]
            ):
                raise ValueError(
                    f"Audit dimension {name} score must be between "
                    f"{score_range['minimum']} and {score_range['maximum']}."
                )
            if item.get("weight") != expected_weight:
                raise ValueError(f"Audit dimension {name} must use weight {expected_weight}.")
            weighted += float(score) * expected_weight / 100
        overall = audit.get("overall_score")
        if not isinstance(overall, (int, float)) or abs(float(overall) - weighted) > 0.05:
            raise ValueError(f"Audit overall_score must equal the weighted score {weighted:.2f}.")
    for key in ("strengths", "gaps"):
        if not isinstance(audit.setdefault(key, []), list):
            raise ValueError(f"Audit field {key} must be an array.")
    for gap in audit["gaps"]:
        if not isinstance(gap, dict) or not all(str(gap.get(key, "")).strip() for key in ("priority", "dimension", "issue", "fix")):
            raise ValueError("Every audit gap requires priority, dimension, issue, and fix.")
        evidence = gap.get("evidence")
        if audit["analysis_status"] == "complete" and (
            not isinstance(evidence, list)
            or not evidence
            or not all(isinstance(item, str) and item.strip() for item in evidence)
        ):
            raise ValueError("Every complete-audit gap requires non-empty evidence.")
    findings = audit.setdefault("knowledge_findings", [])
    if not isinstance(findings, list):
        raise ValueError("Audit knowledge_findings must be an array.")
    for finding in findings:
        if not isinstance(finding, dict) or not all(str(finding.get(key, "")).strip() for key in ("type", "decision", "owner", "projection", "repair", "validation")):
            raise ValueError("Every audit knowledge finding requires type, decision, owner, projection, repair, and validation.")
        if finding["decision"] not in {"promote", "retain", "merge", "retire", "archive-only"}:
            raise ValueError("Audit knowledge finding decision must use the experience lifecycle.")
    entropy = audit.get("entropy_report")
    if entropy is not None and (
        not isinstance(entropy, dict)
        or not isinstance(entropy.get("before"), dict)
        or not isinstance(entropy.get("after"), dict)
    ):
        raise ValueError(
            "Audit entropy_report (documentation duplication report) requires before and after objects."
        )
    return audit


def validate_change_evidence(path: Path) -> tuple[bool, list[str]]:
    required = ("summary.md", "spec.md", "plan.md", "tasks.md", "reviews/review.md")
    issues = [name for name in required if not (path / name).is_file()]
    if issues:
        return False, [f"missing {name}" for name in issues]

    texts = {name: (path / name).read_text(encoding="utf-8") for name in required}
    if CLARIFICATION_RE.search(texts["spec.md"]):
        issues.append("spec.md contains unresolved high-impact clarification")

    plan = texts["plan.md"]
    review = texts["reviews/review.md"]
    if not re.search(
        r"^\s*[-*]\s*(?:Status:\s*approved|Approved:\s*yes)\s*$",
        plan,
        re.IGNORECASE | re.MULTILINE,
    ):
        issues.append("plan.md does not record an approved plan review")
    if not re.search(
        r"^\s*[-*]\s*Approved:\s*yes\s*$",
        review,
        re.IGNORECASE | re.MULTILINE,
    ):
        issues.append("reviews/review.md does not approve the plan")
    acceptance_definitions = list(AC_DEFINITION_RE.finditer(texts["spec.md"]))
    spec_acs = {match.group("id").upper() for match in acceptance_definitions}
    for match in acceptance_definitions:
        value = match.group("value").strip()
        if not value or re.search(r"\bTBD\b", value, re.IGNORECASE):
            issues.append(f"acceptance criterion {match.group('id').upper()} has no completed value")
    task_acs: set[str] = set()
    task_blocks: list[tuple[re.Match[str], list[str]]] = []
    for line in texts["tasks.md"].splitlines():
        match = TASK_RE.match(line.strip())
        if match:
            task_blocks.append((match, [match.group("body")]))
        elif task_blocks:
            task_blocks[-1][1].append(line)
    for match, block_lines in task_blocks:
        block = "\n".join(block_lines)
        task_id = match.group("task")
        if match.group("done").lower() != "x":
            issues.append(f"unfinished task {task_id}")
        task_acs.update(item.upper() for item in AC_RE.findall(block))
        owner_path = task_field_value(block, "owner/path")
        owner = task_field_value(block, "owner")
        target_path = task_field_value(block, "path")
        if not owner_path and not (owner and target_path):
            issues.append(f"task {task_id} has no valid owner/path mapping")
        if not task_field_value(block, "validation"):
            issues.append(f"task {task_id} has no valid validation mapping")
    if not task_blocks:
        issues.append("tasks.md contains no structured tasks")
    for acceptance in sorted(spec_acs - task_acs):
        issues.append(f"acceptance criterion {acceptance} has no task mapping")
    if not spec_acs:
        issues.append("spec.md contains no acceptance criterion")

    return not issues, issues


def load_bound_report(path: Path, kind: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{kind} report is missing or invalid JSON: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ValueError(f"{kind} report must be a schema_version 1.0 object.")
    return value
