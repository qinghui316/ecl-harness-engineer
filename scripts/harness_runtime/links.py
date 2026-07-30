"""Runtime copying, managed routes, connectors, and Codex/Claude project links."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .core import HarnessError, MANAGED_CONNECTOR_MARKER, MANAGED_ROUTE_BEGIN, MANAGED_ROUTE_END, MAX_ROUTE_BYTES, TEXT_SUFFIXES, atomic_write_bytes, atomic_write_text, is_link_like, normalize_path, read_json, reject_linked_ancestors, render, run, safe_relative
from .project import worktree_roots

def distribution_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def scaffold_root() -> Path:
    candidate = distribution_root() / "assets" / "project-skill"
    if not candidate.exists():
        raise HarnessError("Project Harness scaffold is unavailable from this runtime distribution.")
    return candidate

def scaffold_runtime_available() -> bool:
    return (distribution_root() / "assets" / "project-skill").is_dir()

def copy_scaffold(destination: Path, replacements: dict[str, str]) -> None:
    source = scaffold_root()
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        if item.is_dir():
            (destination / relative).mkdir(parents=True, exist_ok=True)
            continue
        target_relative = relative.with_suffix("") if relative.suffix == ".tpl" else relative
        target = destination / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.suffix.lower() in TEXT_SUFFIXES:
            content = item.read_text(encoding="utf-8")
            atomic_write_text(target, render(content, replacements))
        else:
            shutil.copy2(item, target)

def copy_runtime(destination: Path) -> list[str]:
    scripts = destination / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "checks").mkdir(parents=True, exist_ok=True)
    source_root = Path(__file__).resolve().parent.parent
    runtime_names = (
        "harness_cli.py",
        "detect_adapters.py",
        "build_analysis_bundle.py",
        "render_greenfield.py",
        "generate_rule_docs.py",
        "check_project_wiki_stale.py",
        "check_stage_artifacts.py",
    )
    previous_manifest = read_json(destination / "state" / "manifest.json", {})
    previous_launchers = previous_manifest.get("launchers", [])
    if not isinstance(previous_launchers, list):
        raise HarnessError("Project Harness manifest launchers must be an array.")
    expected_top_level = set(runtime_names)
    for value in previous_launchers:
        if not isinstance(value, str):
            raise HarnessError("Project Harness manifest contains a non-string launcher path.")
        relative = Path(safe_relative(value, "Harness-owned runtime path"))
        if len(relative.parts) != 1 or relative.name in expected_top_level:
            continue
        target = scripts / relative
        if target.is_file() or target.is_symlink():
            target.unlink()
    for domain in ("project", "change", "integrate", "evolve", "knowledge"):
        for suffix in ("ps1", "cmd", "sh"):
            stale_launcher = scripts / f"harness-{domain}.{suffix}"
            if stale_launcher.is_file() or stale_launcher.is_symlink():
                stale_launcher.unlink()
    for runtime_name in runtime_names:
        source = source_root / runtime_name
        if not source.is_file():
            raise HarnessError(f"Bundled runtime script is missing: {source}")
        target = scripts / runtime_name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    package_source = source_root / "harness_runtime"
    package_target = scripts / "harness_runtime"
    package_files = sorted(package_source.glob("*.py"))
    if not package_files or not (package_source / "__init__.py").is_file():
        raise HarnessError(f"Bundled Harness runtime package is incomplete: {package_source}")
    if package_source.resolve() != package_target.resolve():
        package_target.mkdir(parents=True, exist_ok=True)
        expected_package = {source.name for source in package_files}
        for existing in package_target.iterdir():
            if existing.name in expected_package and existing.is_file() and not existing.is_symlink():
                continue
            if existing.is_dir() and not existing.is_symlink():
                shutil.rmtree(existing)
            else:
                existing.unlink()
        for source in package_files:
            shutil.copy2(source, package_target / source.name)
    rubric_source = distribution_root() / "references" / "audit-rubric.json"
    if not rubric_source.is_file():
        raise HarnessError(f"Bundled audit rubric is missing: {rubric_source}")
    rubric_target = destination / "references" / "audit-rubric.json"
    rubric_target.parent.mkdir(parents=True, exist_ok=True)
    if rubric_source.resolve() != rubric_target.resolve():
        shutil.copy2(rubric_source, rubric_target)
    domains = ("project", "change", "integrate", "evolve", "knowledge")
    launchers = [*runtime_names, *(f"harness_runtime/{path.name}" for path in package_files)]
    windows_shell = (
        "powershell" if shutil.which("powershell")
        else "pwsh" if shutil.which("pwsh")
        else None
    )
    for domain in domains:
        if os.name == "nt" and windows_shell:
            name = f"harness-{domain}.ps1"
            content = (
                "$ErrorActionPreference = 'Stop'\n"
                "$cli = Join-Path $PSScriptRoot 'harness_cli.py'\n"
                "if ($env:ECL_HARNESS_PYTHON) {\n"
                f"    & $env:ECL_HARNESS_PYTHON $cli {domain} @args\n"
                "} elseif (Get-Command python -ErrorAction SilentlyContinue) {\n"
                f"    & python $cli {domain} @args\n"
                "} elseif (Get-Command py -ErrorAction SilentlyContinue) {\n"
                f"    & py -3 $cli {domain} @args\n"
                "} else {\n"
                "    Write-Error 'Python 3 is required. Install it or set ECL_HARNESS_PYTHON for this host.'\n"
                "    exit 2\n"
                "}\n"
                "exit $LASTEXITCODE\n"
            )
        elif os.name == "nt":
            name = f"harness-{domain}.cmd"
            content = (
                "@echo off\n"
                "if defined ECL_HARNESS_PYTHON goto harness_python_override\n"
                "where python >nul 2>nul\n"
                "if %errorlevel% equ 0 goto harness_python\n"
                "where py >nul 2>nul\n"
                "if %errorlevel% equ 0 goto harness_py\n"
                "echo Python 3 is required. Install it or set ECL_HARNESS_PYTHON for this host. 1>&2\n"
                "exit /b 2\n"
                ":harness_python_override\n"
                f'"%ECL_HARNESS_PYTHON%" "%~dp0harness_cli.py" {domain} %*\n'
                "exit /b %errorlevel%\n"
                ":harness_python\n"
                f'python "%~dp0harness_cli.py" {domain} %*\n'
                "exit /b %errorlevel%\n"
                ":harness_py\n"
                f'py -3 "%~dp0harness_cli.py" {domain} %*\n'
                "exit /b %errorlevel%\n"
            )
        else:
            name = f"harness-{domain}.sh"
            content = (
                "#!/usr/bin/env sh\n"
                "set -eu\n"
                "SCRIPT_DIR=$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd)\n"
                "if [ -n \"${ECL_HARNESS_PYTHON:-}\" ]; then\n"
                f"  exec \"$ECL_HARNESS_PYTHON\" \"$SCRIPT_DIR/harness_cli.py\" {domain} \"$@\"\n"
                "elif command -v python3 >/dev/null 2>&1; then\n"
                f"  exec python3 \"$SCRIPT_DIR/harness_cli.py\" {domain} \"$@\"\n"
                "elif command -v python >/dev/null 2>&1; then\n"
                f"  exec python \"$SCRIPT_DIR/harness_cli.py\" {domain} \"$@\"\n"
                "else\n"
                "  echo 'Python 3 is required. Install it or set ECL_HARNESS_PYTHON for this host.' >&2\n"
                "  exit 2\n"
                "fi\n"
            )
        path = scripts / name
        atomic_write_text(path, content)
        if os.name != "nt":
            path.chmod(path.stat().st_mode | 0o111)
        launchers.append(name)
    return launchers

def same_target(link: Path, target: Path) -> bool:
    try:
        return link.resolve() == target.resolve()
    except OSError:
        return False

def create_directory_link(link: Path, target: Path) -> bool:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        if same_target(link, target):
            return False
        raise HarnessError(f"Runtime Skill path collision: {link}")
    if os.name == "nt":
        result = run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=False)
        if result.returncode != 0:
            raise HarnessError(f"Could not create Windows junction {link}: {result.stderr.strip()}")
    else:
        relative = os.path.relpath(target, link.parent)
        link.symlink_to(relative, target_is_directory=True)
    return True

def remove_directory_link(link: Path, expected_target: Path) -> None:
    if normalize_path(link) == normalize_path(expected_target):
        return
    if not (link.exists() or link.is_symlink()) or not same_target(link, expected_target):
        return
    if link.is_symlink():
        link.unlink()
    else:
        os.rmdir(link)

def runtime_roots(context: dict[str, Any], args: argparse.Namespace) -> list[tuple[str, Path]]:
    del args
    roots: list[tuple[str, Path]] = []
    for worktree in worktree_roots(context):
        roots.append(("codex", worktree / ".agents" / "skills"))
        roots.append(("claude", worktree / ".claude" / "skills"))
    result: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for name, path in roots:
        reject_linked_ancestors(path.parent.parent, path, f"{name} Skill discovery path")
        normalized = normalize_path(path)
        if normalized not in seen:
            result.append((name, path))
            seen.add(normalized)
    return result

def connector_route() -> tuple[str, str]:
    if os.name == "nt" and (shutil.which("powershell") or shutil.which("pwsh")):
        executable = "powershell" if shutil.which("powershell") else "pwsh"
        return (
            "harness-skill-link.ps1",
            f"{executable} -NoProfile -ExecutionPolicy Bypass -File scripts/harness-skill-link.ps1",
        )
    if shutil.which("node"):
        return "harness-skill-link.mjs", "node scripts/harness-skill-link.mjs"
    if shutil.which("python3"):
        return "harness-skill-link.py", "python3 scripts/harness-skill-link.py"
    if shutil.which("python"):
        return "harness-skill-link.py", "python scripts/harness-skill-link.py"
    raise HarnessError(
        "No supported new-worktree connector host is available (PowerShell, Node.js, or Python)."
    )

def generated_command_routes() -> dict[str, str]:
    if os.name == "nt":
        shell = "powershell" if shutil.which("powershell") else "pwsh" if shutil.which("pwsh") else None
        if shell:
            base = f"{shell} -NoProfile -ExecutionPolicy Bypass -File <project-skill-dir>/scripts"
            return {
                domain.upper() + "_COMMAND": f"{base}/harness-{domain}.ps1"
                for domain in ("project", "change", "integrate", "evolve", "knowledge")
            }
        return {
            domain.upper() + "_COMMAND": f"<project-skill-dir>/scripts/harness-{domain}.cmd"
            for domain in ("project", "change", "integrate", "evolve", "knowledge")
        }
    return {
        domain.upper() + "_COMMAND": f"<project-skill-dir>/scripts/harness-{domain}.sh"
        for domain in ("project", "change", "integrate", "evolve", "knowledge")
    }

def ensure_local_skill_excludes(context: dict[str, Any]) -> None:
    if context["mode"] == "single_lane":
        return
    common: Path = context["git_common_dir"]
    exclude = common / "info" / "exclude"
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    lines = existing.splitlines()
    wanted = [
        f"/.agents/skills/{context['skill_name']}",
        f"/.claude/skills/{context['skill_name']}",
        "/.agents/reference-projects/",
        "/.agents/skills/.harness-operation-locks/",
        "/.agents/skills/.*.content-transactions/",
    ]
    changed = False
    for value in wanted:
        if value not in lines:
            lines.append(value)
            changed = True
    if changed:
        atomic_write_text(exclude, "\n".join(lines))

def ensure_runtime_links(
    context: dict[str, Any],
    args: argparse.Namespace,
    skill_root: Path,
) -> tuple[list[dict[str, str]], list[Path]]:
    links: list[dict[str, str]] = []
    created: list[Path] = []
    try:
        for runtime, root in runtime_roots(context, args):
            link = root / context["skill_name"]
            if create_directory_link(link, skill_root):
                created.append(link)
            links.append({
                "runtime": runtime,
                "worktree": str(root.parent.parent),
                "path": str(link),
                "kind": "physical" if normalize_path(link) == normalize_path(skill_root) else "link",
            })
        ensure_local_skill_excludes(context)
    except Exception:
        for link in reversed(created):
            remove_directory_link(link, skill_root)
        raise
    return links, created

def route_replacements(context: dict[str, Any]) -> tuple[dict[str, str], str, str]:
    connector_name, connector_command = connector_route()
    connector_guidance = (
        "If this is a newly created worktree and the Skill is not discoverable yet, run:\n\n"
        f"```text\n{connector_command}\n```\n\n"
        "Then reload the project Harness and run its Registry preflight before planning or implementation."
        if context["mode"] == "multi_lane"
        else "This non-Git project currently uses single-Lane mode; no worktree connector is installed."
    )
    return ({
        "SKILL_NAME": context["skill_name"],
        "PROJECT_NAME": context["project_name"],
        "PROJECT_ID": context["project_id"],
        "MODE": context["mode"],
        "CONNECTOR_COMMAND": connector_command,
        "CONNECTOR_GUIDANCE": connector_guidance,
        **generated_command_routes(),
    }, connector_name, connector_command)

def merge_managed_route(target: Path, rendered: str) -> tuple[str, bytes | None]:
    if is_link_like(target):
        raise HarnessError(f"Route file must not be a link: {target}")
    previous = target.read_bytes() if target.exists() else None
    if previous is not None and len(previous) > MAX_ROUTE_BYTES:
        raise HarnessError(f"Route file is too large for managed-block update: {target}")
    try:
        existing = previous.decode("utf-8") if previous is not None else ""
    except UnicodeDecodeError as exc:
        raise HarnessError(f"Route file is not valid UTF-8: {target}") from exc
    block = f"{MANAGED_ROUTE_BEGIN}\n{rendered.strip()}\n{MANAGED_ROUTE_END}"
    begin_count = existing.count(MANAGED_ROUTE_BEGIN)
    end_count = existing.count(MANAGED_ROUTE_END)
    if begin_count != end_count or begin_count > 1:
        raise HarnessError(f"Route file has malformed Harness managed markers: {target}")
    if begin_count == 1:
        start = existing.index(MANAGED_ROUTE_BEGIN)
        end = existing.index(MANAGED_ROUTE_END, start) + len(MANAGED_ROUTE_END)
        updated = existing[:start] + block + existing[end:]
    else:
        if not existing:
            prefix = ""
        elif existing.endswith(("\n\n", "\r\n\r\n")):
            prefix = existing
        elif existing.endswith(("\n", "\r\n")):
            prefix = existing + "\n"
        else:
            prefix = existing + "\n\n"
        updated = prefix + block + "\n"
    if previous is not None and updated.encode("utf-8") == previous:
        return "unchanged", previous
    atomic_write_text(target, updated)
    return ("updated" if previous is not None else "created"), previous

def install_managed_connector(target: Path, template: Path, replacements: dict[str, str]) -> tuple[str, bytes | None]:
    if is_link_like(target):
        raise HarnessError(f"Connector path collision with a linked file: {target}")
    rendered = render(template.read_text(encoding="utf-8"), replacements)
    previous = target.read_bytes() if target.exists() else None
    if previous is not None:
        try:
            existing = previous.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HarnessError(f"Connector collision is not UTF-8 text: {target}") from exc
        if existing.replace("\r\n", "\n").rstrip() == rendered.replace("\r\n", "\n").rstrip():
            return "unchanged", previous
        if MANAGED_CONNECTOR_MARKER not in existing:
            raise HarnessError(f"Connector path collision with an unmanaged file: {target}")
    atomic_write_text(target, rendered)
    return ("updated" if previous is not None else "created"), previous

def restore_route_snapshots(snapshots: dict[Path, bytes | None]) -> None:
    for path, previous in reversed(list(snapshots.items())):
        if previous is None:
            if path.exists():
                path.unlink()
        else:
            atomic_write_bytes(path, previous)

def ensure_project_routes(
    context: dict[str, Any],
    skill_root: Path,
) -> tuple[dict[str, str], dict[Path, bytes | None]]:
    replacements, connector_name, _ = route_replacements(context)
    templates = skill_root / "assets" / "templates"
    routes: dict[str, str] = {}
    snapshots: dict[Path, bytes | None] = {}
    try:
        reject_linked_ancestors(
            context["project_root"], context["project_root"] / "scripts", "Harness connector path",
        )
        for name in ("AGENTS.md", "CLAUDE.md"):
            target = context["project_root"] / name
            status, previous = merge_managed_route(
                target,
                render((templates / name).read_text(encoding="utf-8"), replacements),
            )
            routes[name] = status
            snapshots[target] = previous
        if context["mode"] == "multi_lane":
            relative = f"scripts/{connector_name}"
            target = context["project_root"] / relative
            status, previous = install_managed_connector(target, templates / connector_name, replacements)
            routes[relative] = status
            snapshots[target] = previous
    except Exception:
        restore_route_snapshots(snapshots)
        raise
    return routes, snapshots

def ensure_all_project_routes(
    context: dict[str, Any],
    skill_root: Path,
) -> tuple[dict[str, dict[str, str]], dict[Path, bytes | None]]:
    # Tracked routes belong to each branch. An explicit operation may repair the
    # invoking worktree, but must not dirty every other worktree behind the user.
    routes, snapshots = ensure_project_routes(context, skill_root)
    return {str(context["project_root"]): routes}, snapshots

def worktree_route_findings(context: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    connector_name, _ = connector_route()
    for worktree in worktree_roots(context):
        for name in ("AGENTS.md", "CLAUDE.md"):
            path = worktree / name
            content = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
            if (
                MANAGED_ROUTE_BEGIN not in content
                or MANAGED_ROUTE_END not in content
                or context["skill_name"] not in content
            ):
                findings.append({
                    "type": "missing_worktree_route",
                    "worktree": str(worktree),
                    "path": str(path),
                })
        if context["mode"] == "multi_lane":
            connector = worktree / "scripts" / connector_name
            content = connector.read_text(encoding="utf-8", errors="replace") if connector.is_file() else ""
            if MANAGED_CONNECTOR_MARKER not in content:
                findings.append({
                    "type": "missing_worktree_connector",
                    "worktree": str(worktree),
                    "path": str(connector),
                })
    return findings
