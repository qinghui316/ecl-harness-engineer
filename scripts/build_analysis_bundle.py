#!/usr/bin/env python3
"""Extract a draft four control-file evidence bundle for Agent semantic review."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SCRIPT_ROOT = Path(__file__).resolve().parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from harness_runtime.core import is_link_like


IGNORED_SOURCE_DIRECTORIES = {
    ".git", ".agents", ".claude", ".tmp", ".local-tools", ".cache",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".turbo",
    "node_modules", "vendor", "dist", "build", "out", "target", "coverage",
    "reference-projects", "generated", ".generated", "tmp", "temp", "__pycache__",
}


def ignored_source_path(path: Path) -> bool:
    return any(part.casefold() in IGNORED_SOURCE_DIRECTORIES for part in path.parts)


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def evidence_file(root: Path, *names: str) -> str | None:
    return next((name for name in names if (root / name).is_file()), None)


def first_readme_paragraph(root: Path) -> tuple[str | None, str | None]:
    readme = evidence_file(root, "README.md", "README.rst", "README.txt")
    if not readme:
        return None, None
    lines = (root / readme).read_text(encoding="utf-8", errors="replace").splitlines()
    paragraphs, current = [], []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "![", "[!")):
            if current:
                paragraphs.append(" ".join(current)); current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))
    return (paragraphs[0] if paragraphs else None), readme


def detect_adapters(root: Path) -> dict:
    script = Path(__file__).with_name("detect_adapters.py")
    result = subprocess.run(
        [sys.executable, str(script), "--project-root", str(root)],
        text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SystemExit(f"adapter detection failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout)


def raise_walk_error(error: OSError) -> None:
    raise error


def source_files(root: Path) -> list[Path]:
    suffixes = {".py", ".go", ".ts", ".tsx", ".js", ".java", ".rs"}
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked.returncode == 0 and tracked.stdout:
        files: list[Path] = []
        for raw in tracked.stdout.split(b"\0"):
            if not raw:
                continue
            relative_path = Path(raw.decode("utf-8", errors="strict"))
            if ignored_source_path(relative_path):
                continue
            path = root / relative_path
            if path.suffix in suffixes and path.is_file() and not is_link_like(path):
                files.append(path)
        if files:
            return sorted(files)
    files: list[Path] = []
    for current, directories, names in os.walk(
        root, topdown=True, onerror=raise_walk_error, followlinks=False,
    ):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories
            if name.casefold() not in IGNORED_SOURCE_DIRECTORIES and not is_link_like(current_path / name)
        )
        files.extend(
            path for name in sorted(names)
            if (path := current_path / name).suffix in suffixes
            and path.is_file()
            and not is_link_like(path)
        )
    return sorted(files)


def source_language(path: Path) -> str:
    return {
        ".py": "python", ".go": "go", ".ts": "typescript", ".tsx": "typescript",
        ".js": "typescript", ".java": "java", ".rs": "rust",
    }.get(path.suffix, "generic")


def resolve_source(root: Path, source: Path, value: str, language: str, files: list[Path]) -> Path | None:
    candidates: list[Path] = []
    if language == "python":
        path = Path(*value.split("."))
        candidates.extend([root / f"{path}.py", root / path / "__init__.py", root / "src" / f"{path}.py", root / "src" / path / "__init__.py"])
    elif language == "typescript" and value.startswith("."):
        base = (source.parent / value).resolve()
        if base.suffix in {".js", ".ts", ".tsx"}:
            base = base.with_suffix("")
        candidates.extend(Path(f"{base}{suffix}") for suffix in (".ts", ".tsx", ".js"))
        candidates.extend(base / f"index{suffix}" for suffix in (".ts", ".tsx", ".js"))
    elif language == "go":
        go_mod = root / "go.mod"
        module_match = re.search(r"(?m)^module\s+(\S+)", go_mod.read_text(encoding="utf-8", errors="replace")) if go_mod.is_file() else None
        if module_match and value.startswith(module_match.group(1) + "/"):
            package = root / value[len(module_match.group(1)) + 1:]
            candidates.extend(path for path in files if path.parent == package)
    elif language == "java":
        path = Path(*value.split("."))
        candidates.extend([root / "src" / "main" / "java" / f"{path}.java", root / f"{path}.java"])
    elif language == "rust" and value.startswith("crate::"):
        path = Path(*value.removeprefix("crate::").split("::"))
        candidates.extend([root / "src" / f"{path}.rs", root / "src" / path / "mod.rs"])
    file_set = {path.resolve(): path for path in files}
    return next((file_set[candidate.resolve()] for candidate in candidates if candidate.resolve() in file_set), None)


def import_values(text: str, language: str) -> list[str]:
    if language == "python":
        return re.findall(r"(?m)^(?:from|import)\s+([A-Za-z0-9_.]+)", text)
    if language == "typescript":
        return re.findall(r"(?:from\s+|require\()['\"]([^'\"]+)", text)
    if language == "go":
        return re.findall(r"[\"`]([^\"`]+)[\"`]", text)
    if language == "java":
        return re.findall(r"(?m)^import\s+([A-Za-z0-9_.]+);", text)
    if language == "rust":
        return re.findall(r"(?m)^use\s+([^;{]+)", text)
    return []


def function_names(text: str, language: str) -> list[str]:
    patterns = {
        "python": r"(?m)^def\s+(\w+)\s*\(", "typescript": r"(?:function|const)\s+(\w+)",
        "go": r"(?m)^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(", "java": r"(?:public|protected|private)\s+(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\(",
        "rust": r"(?m)^(?:pub\s+)?fn\s+(\w+)\s*\(",
    }
    return re.findall(patterns.get(language, r"$^"), text)


def analyze(root: Path, adapters: dict) -> tuple[dict, dict]:
    _, readme = first_readme_paragraph(root)
    files = source_files(root)
    tests = [path for path in files if "test" in path.name.lower() or "tests" in path.parts]
    implementation = [path for path in files if path not in tests]
    manifest = evidence_file(root, "pyproject.toml", "package.json", "go.mod", "Cargo.toml", "pom.xml", "build.gradle")
    languages = [{"name": item["id"].title(), "confidence": "high", "evidence": item.get("evidence", [])} for item in adapters.get("adapters", [])]
    roots = []
    for candidate in ("src", "internal", "cmd", "app", "lib"):
        if (root / candidate).is_dir() and any(path.is_relative_to(root / candidate) for path in implementation):
            evidence = [relative(path, root) for path in implementation if path.is_relative_to(root / candidate)][:3]
            roots.append({"path": candidate, "confidence": "high", "evidence": evidence})
    entry_names = {"main.py", "main.go", "main.rs", "lib.rs", "index.ts", "index.js", "cli.py", "cli.ts", "service.py", "server.ts", "Main.java"}
    entries = [path for path in implementation if path.name in entry_names]
    if not entries and implementation:
        entries = [implementation[0]]
    dependencies = []
    for path in implementation:
        text = path.read_text(encoding="utf-8", errors="replace")
        language = source_language(path)
        for value in import_values(text, language):
            candidate = resolve_source(root, path, value.strip(), language, implementation)
            if candidate and candidate != path:
                dependencies.append({
                    "from": relative(path, root), "to": relative(candidate, root), "relation": "imports",
                    "module_id": None,
                    "evidence": [relative(path, root), relative(candidate, root)],
                })
    dependencies = list({(item["from"], item["to"]): item for item in dependencies}.values())
    module_roots: dict[Path, list[Path]] = {}
    for source in implementation:
        containing = next((root / item["path"] for item in roots if source.is_relative_to(root / item["path"])), source.parent)
        rel_parts = source.relative_to(containing).parts
        module_root = containing / rel_parts[0] if len(rel_parts) > 1 else containing
        module_roots.setdefault(module_root, []).append(source)
    modules = []
    for module_root, module_sources_raw in module_roots.items():
        token = module_root.name.lower().replace("-", "_")
        module_tests = [relative(path, root) for path in tests if token in relative(path, root).lower().replace("-", "_")]
        module_entries = [path for path in entries if path.is_relative_to(module_root)]
        module_edges = [item for item in dependencies if any(item[key].startswith(relative(module_root, root) + "/") or item[key] == relative(module_root, root) for key in ("from", "to"))]
        if not (module_tests or module_entries or module_edges):
            continue
        module_id = re.sub(r"[^a-z0-9]+", "-", module_root.name.lower()).strip("-") or "application"
        modules.append({
            "id": module_id, "name": module_root.name.replace("_", " ").title(),
            "responsibility": f"Own the evidenced behavior rooted at {relative(module_root, root)}.",
            "kind": "evidenced_module", "roots": [relative(module_root, root)],
            "entrypoints": [relative(path, root) for path in module_entries], "interfaces": [],
            "dependencies": sorted({item["to"] for item in module_edges if item["from"].startswith(relative(module_root, root))}),
            "tests": module_tests, "commands": [],
            "boundaries": ["Use the cited entrypoints and dependency edges; do not infer a directory-only boundary."],
            "evidence": list(dict.fromkeys([*[relative(path, root) for path in module_sources_raw[:4]], *module_tests[:2], *[value for item in module_edges[:2] for value in item["evidence"]]])),
        })
    for edge in dependencies:
        edge["module_id"] = next((module["id"] for module in modules if edge["from"].startswith(module["roots"][0])), None)
    interfaces = []
    for path in implementation:
        text = path.read_text(encoding="utf-8", errors="replace")
        language = source_language(path)
        definitions = re.findall(r"class\s+(\w+)\s*\(Protocol\)", text)
        definitions += re.findall(r"(?:export\s+)?interface\s+(\w+)", text) if language == "typescript" else []
        definitions += re.findall(r"(?m)^type\s+(\w+)\s+interface\s*{", text) if language == "go" else []
        definitions += re.findall(r"(?m)(?:public\s+)?interface\s+(\w+)", text) if language == "java" else []
        definitions += re.findall(r"(?m)^(?:pub\s+)?trait\s+(\w+)", text) if language == "rust" else []
        for name in definitions:
            implementations = []
            for candidate in implementation:
                candidate_text = candidate.read_text(encoding="utf-8", errors="replace")
                patterns = [rf"class\s+(\w+)\s*\({name}\)", rf"class\s+(\w+)\s+implements\s+{name}", rf"impl\s+{name}\s+for\s+(\w+)"]
                for pattern in patterns:
                    implementations.extend(f"{relative(candidate, root)}::{value}" for value in re.findall(pattern, candidate_text))
            interfaces.append({
                "name": name, "location": f"{relative(path, root)}::{name}", "implementations": implementations,
                "module_id": next((module["id"] for module in modules if relative(path, root).startswith(module["roots"][0])), None),
                "evidence": list(dict.fromkeys([relative(path, root), *[item.split("::", 1)[0] for item in implementations]])),
            })
    for module in modules:
        module["interfaces"] = [
            item["location"] for item in interfaces if item.get("module_id") == module["id"]
        ]
    code_paths = []
    if dependencies:
        edge = dependencies[0]
        code_paths.append({"name": "Primary evidenced call", "flow": [edge["from"], edge["to"]], "semantic_bridge": False, "evidence": edge["evidence"]})
    commands = []
    for item in adapters.get("configured_commands", []):
        commands.append({
            "purpose": item.get("purpose") or item.get("category") or "Project command",
            "category": item.get("category", "verify"), "command": item["command"],
            "working_directory": ".", "status": "configured", "last_result": "not executed",
            "evidence": item.get("evidence", [manifest] if manifest else []),
        })
    if not commands and manifest and tests:
        if manifest == "pyproject.toml":
            commands.append({"purpose": "Run tests", "category": "test", "command": "python -m pytest", "working_directory": ".", "status": "configured", "last_result": "not executed", "evidence": [manifest]})
        elif manifest == "go.mod":
            commands.append({"purpose": "Run tests", "category": "test", "command": "go test ./...", "working_directory": ".", "status": "configured", "last_result": "not executed", "evidence": [manifest]})
    if (root / "go.mod").is_file() and any(path.suffix == ".go" for path in tests) and not any(item["command"] == "go test ./..." for item in commands):
        commands.append({"purpose": "Run Go tests", "category": "test", "command": "go test ./...", "working_directory": ".", "status": "configured", "last_result": "not executed", "evidence": ["go.mod"]})
    variables = []
    env_example = evidence_file(root, ".env.example", ".env.sample")
    if env_example:
        for line in (root / env_example).read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"([A-Z][A-Z0-9_]*)=", line.strip())
            if match:
                name = match.group(1)
                variables.append({"name": name, "required": True, "sensitive": bool(re.search(r"TOKEN|SECRET|PASSWORD|KEY", name)), "description": "Declared environment variable.", "evidence": [env_example]})
    bridges = []
    represented_languages = {source_language(path) for path in implementation}
    detected_languages = {item["id"] for item in adapters.get("adapters", []) if item["id"] != "generic"}
    language_coverage = not detected_languages or detected_languages.issubset(represented_languages)
    reviewable = bool(
        languages and language_coverage and roots and entries and modules and tests
        and commands and (dependencies or interfaces or code_paths)
    )
    evidence = [item for item in (manifest, relative(entries[0], root) if entries else None) if item]
    status = "partial" if evidence else "bootstrap_only"
    profile = {
        "schema_version": "1.0", "analysis_status": status,
        "project_name": root.name, "purpose": None,
        "primary_flows": [{"name": "Primary evidenced call", "description": "A source import connects the primary project flow.", "evidence": code_paths[0]["evidence"]}] if code_paths else [],
        "languages": languages, "frameworks": [], "package_managers": [], "source_roots": roots,
        "entrypoints": [{"path": relative(entry, root), "kind": "source", "evidence": [relative(entry, root)]} for entry in entries],
        "modules": modules, "commands": commands,
        "environment": {"services": [], "variables": variables, "modes": [], "startup_order": [], "helpers": [], "unknowns": [], "evidence": [env_example] if env_example else []},
        "document_candidates": ([{"path": readme, "kind": "repository-prose"}] if readme else []),
        "ci": [{"path": relative(path, root), "evidence": [relative(path, root)]} for path in sorted((root / ".github" / "workflows").glob("*")) if path.is_file()],
        "bridges": bridges, "reference_projects": [], "global_boundaries": [],
        "unknowns": [
            "Agent semantic review is required before this draft can be marked complete."
            if reviewable else "Project evidence is insufficient for semantic completion."
        ],
        "evidence": evidence,
    }
    architecture = {"schema_version": "1.0", "analysis_status": profile["analysis_status"], "layers": [{"level": 0, "packages": [item["path"] for item in roots], "description": "Evidenced source roots.", "evidence": [value for item in roots for value in item["evidence"]]}] if roots else [], "dependencies": dependencies, "components": [], "circular_dependencies": [], "key_interfaces": interfaces, "code_paths": code_paths, "error_patterns": {}, "evidence": list(dict.fromkeys([value for item in dependencies + interfaces + code_paths for value in item.get("evidence", [])]))}
    return profile, architecture


def draft_audit_and_delta(profile: dict) -> tuple[dict, dict]:
    status = profile["analysis_status"]
    audit = {
        "schema_version": "1.0",
        "analysis_status": status,
        "dimensions": {},
        "strengths": [],
        "gaps": [],
        "knowledge_findings": [],
    }
    delta = {
        "schema_version": "1.0",
        "mode": "draft" if status == "partial" else "bootstrap",
        "decisions": [],
        "artifacts": [],
    }
    return audit, delta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.project_root.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit("Analysis output must be empty.")
    output.mkdir(parents=True, exist_ok=True)
    adapters = detect_adapters(root)
    profile, architecture = analyze(root, adapters)
    audit, delta = draft_audit_and_delta(profile)
    for name, value in (("project-profile.json", profile), ("architecture.json", architecture), ("audit.json", audit), ("creation-delta.json", delta)):
        (output / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({
        "analysis_status": profile["analysis_status"],
        "producer_chain": ["deterministic-evidence-extractor"],
        "requires_agent_review": True,
        "output": str(output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
