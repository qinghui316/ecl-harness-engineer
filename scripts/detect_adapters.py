#!/usr/bin/env python3
"""Detect evidence-backed project adapters and configured commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MANIFESTS = {
    "go": ("go.mod",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"),
    "python": ("pyproject.toml", "requirements.txt", "setup.py"),
    "rust": ("Cargo.toml",),
    "typescript": ("package.json", "tsconfig.json",),
}


def safe_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Project root is not a directory: {root}")
    return root


def package_commands(root: Path, manifest: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    scripts = value.get("scripts", {}) if isinstance(value, dict) else {}
    if not isinstance(scripts, dict):
        return []
    result = []
    for name, body in sorted(scripts.items()):
        if not isinstance(body, str) or not body.strip():
            continue
        relative = manifest.relative_to(root).as_posix()
        result.append({
            "purpose": name,
            "category": name if name in {"build", "test", "lint", "typecheck", "start", "dev"} else "task",
            "command": f"npm run {name}",
            "working_directory": manifest.parent.relative_to(root).as_posix() or ".",
            "status": "configured",
            "last_result": "not executed",
            "evidence": [relative],
        })
    return result


def discover(root: Path) -> dict[str, Any]:
    adapters = []
    commands: list[dict[str, Any]] = []
    for adapter_id, names in MANIFESTS.items():
        evidence = []
        for name in names:
            evidence.extend(
                path.relative_to(root).as_posix()
                for path in root.glob(f"**/{name}")
                if not any(part in {".git", "node_modules", "vendor", "target", "dist", "build"} for part in path.parts)
            )
        evidence = sorted(set(evidence))
        if not evidence:
            continue
        adapters.append({
            "id": adapter_id,
            "status": "selected",
            "confidence": "high",
            "evidence": evidence,
        })
        if adapter_id == "typescript":
            for relative in evidence:
                if relative.endswith("package.json"):
                    commands.extend(package_commands(root, root / relative))
    if not adapters:
        generic_evidence = [
            name for name in ("Makefile", "Justfile", "Taskfile.yml", "README.md")
            if (root / name).is_file()
        ]
        adapters.append({
            "id": "generic",
            "status": "selected",
            "confidence": "medium" if generic_evidence else "low",
            "evidence": generic_evidence,
        })
    return {
        "schema_version": "1.0",
        "project_root": str(root),
        "adapters": adapters,
        "configured_commands": commands,
        "note": "Adapter reference defaults remain candidates until project evidence configures them.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    try:
        result = discover(safe_root(args.project_root))
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
