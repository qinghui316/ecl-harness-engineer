#!/usr/bin/env python3
"""Validate generated workflow contracts and optional Change stage artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_SECTIONS = (
    "Inputs", "Agent Judgment", "Deterministic Commands", "Actions", "Outputs", "Exit",
    "Stop And Escalate", "Rules",
)
CHANGE_FILES = {
    "intake": ("summary.md", "spec.md"),
    "locate": ("summary.md", "spec.md", "plan.md"),
    "plan": ("summary.md", "spec.md", "plan.md", "tasks.md", "reviews/review.md"),
    "implement": ("summary.md", "spec.md", "plan.md", "tasks.md", "reviews/review.md"),
    "verify": ("summary.md", "spec.md", "plan.md", "tasks.md", "reviews/review.md"),
    "close": ("summary.md", "spec.md", "plan.md", "tasks.md", "reviews/review.md"),
}
ID_MAX_LENGTH = 96


def canonical_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty identifier.")
    raw = value.strip()
    if any(character in raw for character in ("/", "\\", "\0")) or raw in {".", ".."}:
        raise ValueError(f"{label} must not contain path separators or traversal segments.")
    if not re.search(r"[A-Za-z0-9]", raw):
        raise ValueError(f"{label} must contain at least one letter or digit.")
    canonical = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if len(canonical) > ID_MAX_LENGTH:
        raise ValueError(f"{label} exceeds {ID_MAX_LENGTH} canonical characters.")
    return canonical


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--change-id")
    args = parser.parse_args()
    try:
        stage = canonical_id(args.stage, "Stage")
        change_id = canonical_id(args.change_id, "Change id") if args.change_id else None
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    skill_root = args.skill_root.resolve()
    workflow = skill_root / "references" / "workflows" / f"{stage}.md"
    findings: list[dict] = []
    if not workflow.is_file():
        findings.append({"type": "missing_workflow", "path": str(workflow)})
    else:
        text = workflow.read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            if f"## {section}" not in text:
                findings.append({"type": "missing_section", "section": section, "path": str(workflow)})
    if change_id and stage in CHANGE_FILES:
        change = skill_root / "state" / "changes" / "active" / change_id
        for relative in CHANGE_FILES[stage]:
            if not (change / relative).is_file():
                findings.append({"type": "missing_change_artifact", "path": str(change / relative)})
    print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
