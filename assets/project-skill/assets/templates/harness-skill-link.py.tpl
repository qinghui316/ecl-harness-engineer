#!/usr/bin/env python3
# ECL-HARNESS-CONNECTOR
"""Attach this worktree to its project-local shared Harness Skill."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


SKILL_NAME = "{{SKILL_NAME}}"
PROJECT_ID = "{{PROJECT_ID}}"


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def same_target(path: Path, target: Path) -> bool:
    try:
        return path.resolve() == target.resolve()
    except OSError:
        return False


def is_link_like(path: Path) -> bool:
    is_junction = getattr(os.path, "isjunction", None)
    return path.is_symlink() or bool(is_junction and is_junction(path))


def reject_linked_ancestors(root: Path, path: Path) -> None:
    root = Path(os.path.abspath(root))
    parent = Path(os.path.abspath(path.parent))
    try:
        relative = parent.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Skill path escapes this worktree: {path}") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if (current.exists() or current.is_symlink()) and is_link_like(current):
            raise RuntimeError(f"Skill path must not traverse a link or junction: {current}")


def link_directory(root: Path, path: Path, target: Path) -> str:
    if path.resolve(strict=False) == target.resolve(strict=False):
        return "physical"
    reject_linked_ancestors(root, path)
    if path.exists() or path.is_symlink():
        if same_target(path, target):
            return "existing"
        raise RuntimeError(f"Skill path collision: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(path), str(target)],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"could not create junction {path}")
    else:
        path.symlink_to(os.path.relpath(target, path.parent), target_is_directory=True)
    return "created"


def remove_created_link(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        os.rmdir(path)


def main() -> int:
    current = Path.cwd().resolve()
    root = Path(git("rev-parse", "--show-toplevel", cwd=current)).resolve()
    common_raw = git("rev-parse", "--git-common-dir", cwd=root)
    common = Path(common_raw)
    if not common.is_absolute():
        common = (root / common).resolve()
    worktrees = git("worktree", "list", "--porcelain", cwd=root).splitlines()
    primary_line = next((line for line in worktrees if line.startswith("worktree ")), None)
    if common.name == ".git" and common.parent.is_dir():
        primary = common.parent.resolve()
    elif primary_line:
        primary = Path(primary_line.removeprefix("worktree ").strip()).resolve()
    else:
        raise RuntimeError("could not resolve the primary worktree")
    canonical = primary / ".agents" / "skills" / SKILL_NAME
    if not (canonical / "SKILL.md").is_file():
        raise RuntimeError(f"canonical project Harness is missing: {canonical}")
    is_junction = getattr(os.path, "isjunction", None)
    if canonical.is_symlink() or (is_junction and is_junction(canonical)):
        raise RuntimeError(f"canonical project Harness must be physical: {canonical}")
    manifest = json.loads((canonical / "state" / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("project_id") != PROJECT_ID
        or manifest.get("skill_name") != SKILL_NAME
    ):
        raise RuntimeError("canonical project Harness manifest does not match this Git project")
    links = {
        "codex": root / ".agents" / "skills" / SKILL_NAME,
        "claude": root / ".claude" / "skills" / SKILL_NAME,
    }
    result = {}
    created = []
    try:
        for name, path in links.items():
            status = link_directory(root, path, canonical)
            result[name] = {"path": str(path), "status": status}
            if status == "created":
                created.append(path)
    except Exception:
        for path in reversed(created):
            remove_created_link(path)
        raise
    print(json.dumps({"ok": True, "skill": str(canonical), "links": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
