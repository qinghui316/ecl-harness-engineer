#!/usr/bin/env python3
"""Check generated project-wiki evidence fingerprints without rewriting knowledge."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_local_evidence(value: str) -> bool:
    return not value.startswith(("http://", "https://", "user:", "contract:", "registry:"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    skill_root = args.skill_root.resolve()
    manifest_path = skill_root / "state" / "manifest.json"
    index_path = skill_root / "references" / "project_wiki" / "index.json"
    if not manifest_path.exists() or not index_path.exists():
        print(json.dumps({"ok": False, "error": "manifest or project_wiki index is missing"}, indent=2))
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    project_root = (args.project_root or Path(manifest["project_root"])).resolve()
    findings: list[dict] = []
    checked = 0
    for item in index.get("items", []):
        fingerprints = item.get("source_fingerprints", {})
        for relative, expected in fingerprints.items():
            if not is_local_evidence(relative):
                continue
            source = (project_root / relative).resolve()
            try:
                source.relative_to(project_root)
            except ValueError:
                findings.append({"type": "outside_project", "source": relative, "item": item.get("id")})
                continue
            checked += 1
            if not source.is_file():
                findings.append({"type": "missing", "source": relative, "item": item.get("id")})
            elif sha256(source) != expected:
                findings.append({"type": "changed", "source": relative, "item": item.get("id")})
    print(
        json.dumps(
            {"ok": not findings, "checked": checked, "findings": findings},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
