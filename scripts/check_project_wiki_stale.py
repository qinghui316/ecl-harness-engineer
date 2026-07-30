#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical read-only knowledge fingerprint scan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_ROOT = Path(__file__).resolve().parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from harness_runtime.core import HarnessError, read_json
from harness_runtime.knowledge import knowledge_fingerprint_scan
from harness_runtime.project import project_context
from harness_runtime.transactions import project_skill_read_guard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    skill_root = args.skill_root.resolve()
    try:
        manifest = read_json(skill_root / "state" / "manifest.json", {})
        project_root = args.project_root or manifest.get("project_root")
        if not project_root:
            raise HarnessError("Project root is unavailable from arguments and manifest.")
        with project_skill_read_guard(skill_root):
            result = knowledge_fingerprint_scan(skill_root, project_context(Path(project_root)))
    except (HarnessError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
