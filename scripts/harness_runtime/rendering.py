"""Project Wiki, rules, workflows, artifacts, and analysis publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .analysis import evidence_values, reference_project_sources, validate_project_evidence
from .core import HarnessError, SCHEMA_VERSION, TEXT_SUFFIXES, atomic_write_json, atomic_write_text, file_fingerprint, is_within, read_json, run, safe_relative, slugify, stable_hash, utc_now
from .knowledge import context_source_fingerprints
from .project import primary_worktree_root

def markdown_items(values: list[Any], empty: str) -> list[str]:
    lines = []
    for value in values:
        if isinstance(value, dict):
            label = value.get("name") or value.get("summary") or value.get("path") or value.get("id")
            detail = value.get("description") or value.get("purpose")
            if label:
                lines.append(f"- {label}" + (f": {detail}" if detail else ""))
        elif str(value).strip():
            lines.append(f"- {value}")
    return lines or [f"- {empty}"]

def mermaid_node(value: str) -> tuple[str, str]:
    label = str(value).replace('"', "'").replace("\n", " ").strip()
    return f"n{stable_hash(label, 10)}", label

def mermaid_dependency_graph(dependencies: list[dict[str, Any]]) -> list[str]:
    if not dependencies:
        return []
    lines = ["```mermaid", "flowchart LR"]
    declared: set[str] = set()
    for dependency in dependencies:
        source_id, source_label = mermaid_node(dependency["from"])
        target_id, target_label = mermaid_node(dependency["to"])
        for identifier, label in ((source_id, source_label), (target_id, target_label)):
            if identifier not in declared:
                lines.append(f'    {identifier}["{label}"]')
                declared.add(identifier)
        relation = str(dependency.get("relation", "depends on")).replace('"', "'")
        lines.append(f'    {source_id} -->|"{relation}"| {target_id}')
    return [*lines, "```"]

def mermaid_interface_graph(interfaces: list[dict[str, Any]]) -> list[str]:
    edges = [
        {"from": interface.get("location") or interface.get("name"), "to": implementation, "relation": "implemented by"}
        for interface in interfaces
        for implementation in interface.get("implementations", [])
    ]
    return mermaid_dependency_graph(edges)

def mermaid_sequence(path: dict[str, Any]) -> list[str]:
    flow = [str(item).strip() for item in path.get("flow", []) if str(item).strip()]
    if len(flow) < 2:
        return []
    lines = ["```mermaid", "sequenceDiagram"]
    ids: list[str] = []
    for item in flow:
        identifier, label = mermaid_node(item)
        ids.append(identifier)
        lines.append(f"    participant {identifier} as {label}")
    for source, target in zip(ids, ids[1:]):
        lines.append(f"    {source}->>{target}: call / transfer")
    return [*lines, "```"]

def render_project_wiki(
    skill_root: Path,
    context: dict[str, Any],
    profile: dict[str, Any],
    architecture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root: Path = context["project_root"]
    reference_root = primary_worktree_root(context)
    wiki = skill_root / "references" / "project_wiki"
    for directory in ("modules", "systems", "bridges", "reference_projects/maps"):
        (wiki / directory).mkdir(parents=True, exist_ok=True)
    previous = read_json(wiki / "index.json", {})
    for item in previous.get("items", []):
        if item.get("generated_by") != "project-profile":
            continue
        relative = item.get("path")
        if not isinstance(relative, str) or relative == "overview.md":
            continue
        target = wiki / relative
        if target.is_file() and is_within(target, wiki):
            target.unlink()

    purpose = profile.get("purpose") or {}
    modules = profile.get("modules", [])
    commands = profile.get("commands", [])
    documents = profile.get("documents", [])
    boundaries = profile.get("global_boundaries", [])
    reference_projects = profile.get("reference_projects", [])
    references_by_id = {item["id"]: item for item in reference_projects}
    global_references = [item for item in reference_projects if item.get("global_relevance")]
    overview = [
        f"# {profile.get('project_name', context['project_name'])} Project Overview",
        "",
        f"Project id: `{context['project_id']}`",
        f"Analysis status: `{profile.get('analysis_status', 'complete')}`",
        "",
        "## Purpose",
        "",
        purpose.get("summary") or "Unknown. Run evidence-backed project analysis before treating this bootstrap as a mature Harness.",
        "",
        "## Primary Flows",
        "",
        *markdown_items(profile.get("primary_flows", []), "No source-backed primary flow recorded."),
        "",
        "## Major Modules",
        "",
        "| Module | Responsibility | L2 |",
        "| --- | --- | --- |",
        *(
            [f"| {item['name']} | {item['responsibility']} | [map](modules/{item['id']}.md) |" for item in modules]
            or ["| None recorded | Run analyzer before adding module pages | - |"]
        ),
        "",
        "## Canonical Documents",
        "",
        *markdown_items(documents, "No canonical document recorded."),
        "",
        "## Common Commands",
        "",
        *([f"- `{item['command']}` - {item['purpose']} ({item['status']})" for item in commands] or ["- No configured command recorded."]),
        "",
        "## System Maps",
        "",
        *(
            (["- [Commands](systems/commands.md)"] if commands else [])
            + (["- [Environment](systems/environment.md)"] if any((profile.get("environment") or {}).get(key) for key in ("services", "variables", "modes", "startup_order", "helpers", "unknowns")) else [])
            + (["- [Verification](systems/verification.md)"] if any(item.get("category") in {"test", "lint", "typecheck", "build", "verify"} for item in commands) else [])
            + (["- [Architecture](systems/architecture.md)"] if architecture and any(architecture.get(key) for key in ("layers", "circular_dependencies", "key_interfaces", "code_paths", "error_patterns")) else [])
            + (["- [Reference Projects](reference_projects/index.md)"] if reference_projects else [])
            or ["- No evidenced system map recorded."]
        ),
        "",
        "## Global Boundaries",
        "",
        *markdown_items(boundaries, "No project-specific global boundary recorded."),
        "",
        "## Reference Foundations",
        "",
        *(
            [
                f"- {item['global_relevance']} ([{item['name']}](reference_projects/maps/{item['id']}.md))"
                for item in global_references
            ]
            or ["- No project-wide reference foundation recorded; module-specific references remain in L2/L3."]
        ),
        "",
        "## Unknowns",
        "",
        *markdown_items(profile.get("unknowns", []), "No unresolved project-analysis unknown recorded."),
    ]
    overview_text = "\n".join(overview)
    atomic_write_text(wiki / "overview.md", overview_text)

    index_items: list[dict[str, Any]] = []
    for module in modules:
        sources = evidence_values(module)
        reference_relations = module.get("reference_sources", [])
        for relation in reference_relations:
            sources.extend(relation["target_evidence"])
            sources.extend(reference_project_sources(
                reference_root, references_by_id[relation["reference_id"]], relation["reference_evidence"]
            ))
        sources = list(dict.fromkeys(sources))
        local_dependencies = [
            item for item in (architecture or {}).get("dependencies", [])
            if item.get("module_id") == module["id"]
        ]
        local_interfaces = [
            item for item in (architecture or {}).get("key_interfaces", [])
            if item.get("module_id") == module["id"]
        ]
        interface_graph = mermaid_interface_graph(local_interfaces)
        content = [
            f"# {module['name']}", "",
            "## Responsibility", "", module["responsibility"], "",
            "## Source Roots", "", *markdown_items([f"`{value}`" for value in module["roots"]], "No root recorded."), "",
            "## Entrypoints", "", *markdown_items([f"`{value}`" for value in module["entrypoints"]], "No entrypoint recorded."), "",
            "## Interfaces And Dependencies", "",
            *markdown_items(module["interfaces"], "No key interface recorded."),
            *markdown_items(module["dependencies"], "No dependency note recorded."), "",
            "## Local Architecture", "",
            *(
                ["### Dependencies", "", *mermaid_dependency_graph(local_dependencies), ""]
                if local_dependencies else ["No evidenced local dependency graph recorded.", ""]
            ),
            *(["### Interface Implementations", "", *interface_graph, ""] if interface_graph else []),
            "## Tests And Commands", "",
            *markdown_items(module["tests"], "No module-specific test recorded."),
            *markdown_items(module["commands"], "No module-specific command recorded."), "",
            "## Boundaries", "", *markdown_items(module["boundaries"], "No module-specific boundary recorded."), "",
            "## Reference Implementations", "",
            *(
                [
                    f"- [{references_by_id[item['reference_id']]['name']}](../reference_projects/maps/{item['reference_id']}.md): "
                    f"{item['mechanism']} Adaptation: {item['adaptation']} "
                    f"Boundaries: {'; '.join(item.get('boundaries', [])) or 'none recorded'}. "
                    f"Validation: {item['validation']}."
                    for item in reference_relations
                ]
                or ["- No evidence-backed reference implementation is linked to this module."]
            ),
            "",
            "## Evidence", "", *[f"- `{value}`" for value in sources],
        ]
        relative = Path("modules") / f"{module['id']}.md"
        atomic_write_text(wiki / relative, "\n".join(content))
        index_items.append({
            "id": module["id"], "layer": "L2", "kind": "module", "path": relative.as_posix(),
            "sources": sources, "source_fingerprints": context_source_fingerprints(context, sources),
            "content_fingerprint": file_fingerprint([wiki / relative], wiki),
            "generated_by": "project-profile", "updated_at": utc_now(),
        })

    systems: list[tuple[str, str, list[str], list[str]]] = []
    if commands:
        lines = [
            "# Project Commands", "", "Commands retain their evidence status; candidates are not configured facts.", "",
            "| Purpose | Command | Status | Working Directory | Evidence |",
            "| --- | --- | --- | --- | --- |",
        ]
        sources: list[str] = []
        for command in commands:
            evidence = evidence_values(command)
            sources.extend(evidence)
            lines.append(
                f"| {command['purpose']} | `{command['command']}` | {command['status']} | "
                f"`{command.get('working_directory', '.')}` | {', '.join(f'`{value}`' for value in evidence)} |"
            )
        systems.append(("commands", "commands.md", lines, list(dict.fromkeys(sources))))
    environment = profile.get("environment", {})
    if any(environment.get(key) for key in ("services", "variables", "modes", "startup_order", "helpers", "unknowns")):
        sources = list(dict.fromkeys([
            *environment.get("evidence", []),
            *(
                value
                for key in ("services", "variables", "modes", "helpers")
                for item in environment.get(key, [])
                for value in evidence_values(item)
            ),
        ]))
        lines = [
            "# Project Environment", "",
            "## Services", "",
            "| Service | Purpose | Startup Order | Readiness | Migration/Seed | Cleanup | Evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for service in environment.get("services", []):
            readiness = service.get("readiness") or {}
            readiness_text = readiness.get("type", "unknown")
            target = readiness.get("target") or readiness.get("url") or readiness.get("port") or readiness.get("pattern")
            if target not in (None, ""):
                readiness_text += f": {target}"
            lines.append(
                f"| {service['name']} | {service.get('purpose', service.get('description', ''))} | "
                f"{service.get('startup_order', '')} | {readiness_text} | "
                f"{service.get('migration_seed', '')} | {service.get('cleanup', '')} | "
                f"{', '.join(f'`{item}`' for item in evidence_values(service))} |"
            )
        if not environment.get("services"):
            lines.append("| None recorded | - | - | - | - | - | - |")
        lines.extend([
            "", "## Variables", "",
            "| Name | Required | Sensitive | Purpose | Evidence |",
            "| --- | --- | --- | --- | --- |",
        ])
        for variable in environment.get("variables", []):
            lines.append(
                f"| `{variable['name']}` | {variable.get('required', 'unknown')} | "
                f"{variable.get('sensitive', 'unknown')} | {variable.get('description', variable.get('purpose', ''))} | "
                f"{', '.join(f'`{item}`' for item in evidence_values(variable))} |"
            )
        if not environment.get("variables"):
            lines.append("| None recorded | - | - | - | - |")
        lines.extend([
            "", "## Runtime Modes", "", *markdown_items(environment.get("modes", []), "No runtime mode recorded."), "",
            "## Startup Order", "", *markdown_items(environment.get("startup_order", []), "No startup order recorded."), "",
            "## Readiness And Cleanup Helpers", "", *markdown_items(environment.get("helpers", []), "No helper recorded."), "",
            "## Unknown Prerequisites", "", *markdown_items(environment.get("unknowns", []), "No environment unknown recorded."), "",
            "## Evidence", "", *[f"- `{value}`" for value in sources],
        ])
        systems.append(("environment", "environment.md", lines, sources))
    verification = [item for item in commands if item.get("category") in {"test", "lint", "typecheck", "build", "verify"}]
    if verification:
        sources = list(dict.fromkeys(value for item in verification for value in evidence_values(item)))
        lines = [
            "# Project Verification", "",
            "| Gate | Command | Status | Last Result |",
            "| --- | --- | --- | --- |",
            *[
                f"| {item['purpose']} | `{item['command']}` | {item['status']} | {item.get('last_result', 'not executed')} |"
                for item in verification
            ],
        ]
        systems.append(("verification", "verification.md", lines, sources))
    for identifier, filename, lines, sources in systems:
        relative = Path("systems") / filename
        atomic_write_text(wiki / relative, "\n".join(lines))
        index_items.append({
            "id": identifier, "layer": "L2", "kind": "system", "path": relative.as_posix(),
            "sources": sources, "source_fingerprints": context_source_fingerprints(context, sources),
            "content_fingerprint": file_fingerprint([wiki / relative], wiki),
            "generated_by": "project-profile", "updated_at": utc_now(),
        })

    for bridge in profile.get("bridges", []):
        sources = list(dict.fromkeys(value for mapping in bridge["mappings"] for value in evidence_values(mapping)))
        for mapping in bridge["mappings"]:
            reference_id = mapping.get("reference_id")
            if reference_id:
                sources.extend(reference_project_sources(
                    reference_root, references_by_id[reference_id], mapping["reference_evidence"]
                ))
        sources = list(dict.fromkeys(sources))
        lines = [
            f"# {bridge.get('title', bridge['id'])}", "",
            bridge.get("purpose", "Project-specific semantic translations backed by canonical evidence."), "",
            "| Project/Domain Term | Code/Runtime Owner | Evidence |",
            "| --- | --- | --- |",
        ]
        for mapping in bridge["mappings"]:
            reference_id = mapping.get("reference_id")
            reference_note = ""
            if reference_id:
                reference_note = (
                    f"; [{references_by_id[reference_id]['name']}](../reference_projects/maps/{reference_id}.md) "
                    f"at `{', '.join(mapping['reference_evidence'])}`"
                )
            lines.append(
                f"| {mapping['from']} | {mapping['to']} | "
                f"{', '.join(f'`{value}`' for value in evidence_values(mapping))}{reference_note} |"
            )
        relative = Path("bridges") / f"{bridge['id']}.md"
        atomic_write_text(wiki / relative, "\n".join(lines))
        index_items.append({
            "id": bridge["id"], "layer": "L3", "kind": "bridge", "path": relative.as_posix(),
            "sources": sources, "source_fingerprints": context_source_fingerprints(context, sources),
            "content_fingerprint": file_fingerprint([wiki / relative], wiki),
            "generated_by": "project-profile", "updated_at": utc_now(),
        })

    for code_path in (architecture or {}).get("code_paths", []):
        if not code_path.get("semantic_bridge"):
            continue
        diagram = mermaid_sequence(code_path)
        if not diagram:
            continue
        sources = evidence_values(code_path)
        identifier = f"critical-flow-{slugify(str(code_path.get('name', 'flow')))}"
        relative = Path("bridges") / f"{identifier}.md"
        lines = [
            f"# {code_path.get('name', 'Critical Flow')}", "",
            "This sequence is an evidence-backed semantic/runtime bridge.", "",
            *diagram, "", "## Evidence", "", *[f"- `{value}`" for value in sources],
        ]
        atomic_write_text(wiki / relative, "\n".join(lines))
        index_items.append({
            "id": identifier, "layer": "L3", "kind": "bridge", "path": relative.as_posix(),
            "sources": sources, "source_fingerprints": context_source_fingerprints(context, sources),
            "content_fingerprint": file_fingerprint([wiki / relative], wiki),
            "generated_by": "project-profile", "updated_at": utc_now(),
        })

    if reference_projects:
        reference_index_lines = [
            "# Reference Projects", "",
            "Use the reference links already present in relevant L2/L3 project maps. Start here when the task is direct reference research.",
            "",
            "| Reference | Purpose | Applicable Problems | Inspected Commit | Map | Referenced By |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        reference_index_sources: list[str] = []
        for reference in reference_projects:
            reference_id = reference["id"]
            module_links = [
                f"[L2 {module['name']}](../modules/{module['id']}.md)"
                for module in modules
                if any(item.get("reference_id") == reference_id for item in module.get("reference_sources", []))
            ]
            bridge_links = [
                f"[L3 {bridge.get('title', bridge['id'])}](../bridges/{bridge['id']}.md)"
                for bridge in profile.get("bridges", [])
                if any(item.get("reference_id") == reference_id for item in bridge.get("mappings", []))
            ]
            usage_links = [*module_links, *bridge_links]
            map_usage_links = [value.replace("](../", "](../../") for value in usage_links]
            reference_index_lines.append(
                f"| {reference['name']} | {reference['purpose']} | "
                f"{'; '.join(reference['applicable_problems']) or 'Not separately classified'} | "
                f"`{reference['inspected_commit']}` | [source map](maps/{reference_id}.md) | "
                f"{', '.join(usage_links) or 'No target relationship recorded'} |"
            )
            reference_sources = reference_project_sources(reference_root, reference, evidence_values(reference))
            for reference_module in reference["modules"]:
                reference_sources.extend(reference_project_sources(
                    reference_root, reference, evidence_values(reference_module)
                ))
            reference_sources = list(dict.fromkeys(reference_sources))
            reference_index_sources.extend(reference_sources)
            map_lines = [
                f"# Reference: {reference['name']}", "",
                "## Source", "",
                f"- Source: {reference['source']}",
                f"- Local checkout: `{reference['checkout']}`",
                f"- Inspected commit: `{reference['inspected_commit']}`",
                f"- License evidence: {reference.get('license', 'Unknown')}",
                "",
                "## Purpose", "", reference["purpose"], "",
                "## Applicable Problems", "",
                *markdown_items(reference["applicable_problems"], "No separate problem category recorded."),
                "",
                "## Inspected Files", "",
                "| File | Reason |",
                "| --- | --- |",
                *(
                    [f"| `{item['path']}` | {item['reason']} |" for item in reference["inspected_files"]]
                    or ["| No individual file recorded | Use module evidence below |"]
                ),
                "",
                "## Source Map", "",
            ]
            for reference_module in reference["modules"]:
                map_lines.extend([
                    f"### {reference_module['name']}", "",
                    reference_module["responsibility"], "",
                    "- Roots: " + (", ".join(f"`{value}`" for value in reference_module["roots"]) or "none recorded"),
                    "- Entrypoints: " + (", ".join(f"`{value}`" for value in reference_module["entrypoints"]) or "none recorded"),
                    "- Interfaces: " + (", ".join(str(value) for value in reference_module["interfaces"]) or "none recorded"),
                    "- Call paths: " + ("; ".join(str(value) for value in reference_module["call_paths"]) or "none recorded"),
                    "- Tests: " + (", ".join(f"`{value}`" for value in reference_module["tests"]) or "none recorded"),
                    "- Evidence: " + ", ".join(f"`{value}`" for value in evidence_values(reference_module)),
                    "",
                ])
            map_lines.extend([
                "## Current Project Relationships", "",
                *(
                    [f"- {value}" for value in map_usage_links]
                    or ["- No current-project relationship has been accepted yet." ]
                ),
                "",
                "## Boundaries And Unknowns", "",
                *markdown_items(reference["unknowns"], "No unresolved reference-analysis unknown recorded."),
                "",
                "## Evidence", "",
                *[f"- `{value}`" for value in reference_sources],
            ])
            relative = Path("reference_projects") / "maps" / f"{reference_id}.md"
            atomic_write_text(wiki / relative, "\n".join(map_lines))
            index_items.append({
                "id": f"reference-{reference_id}", "layer": "reference", "kind": "reference-map",
                "path": relative.as_posix(), "sources": reference_sources,
                "source_fingerprints": context_source_fingerprints(context, reference_sources),
                "content_fingerprint": file_fingerprint([wiki / relative], wiki),
                "generated_by": "project-profile", "updated_at": utc_now(),
            })
        reference_index_relative = Path("reference_projects") / "index.md"
        atomic_write_text(wiki / reference_index_relative, "\n".join(reference_index_lines))
        reference_index_sources = list(dict.fromkeys(reference_index_sources))
        index_items.append({
            "id": "reference-projects", "layer": "index", "kind": "reference-index",
            "path": reference_index_relative.as_posix(), "sources": reference_index_sources,
            "source_fingerprints": context_source_fingerprints(context, reference_index_sources),
            "content_fingerprint": file_fingerprint([wiki / reference_index_relative], wiki),
            "generated_by": "project-profile", "updated_at": utc_now(),
        })

    overview_sources: list[str] = []
    overview_items = [
        *([purpose] if purpose else []),
        *profile.get("primary_flows", []),
        *modules,
        *commands,
        *documents,
        *boundaries,
    ]
    for item in overview_items:
        if isinstance(item, dict) and item.get("evidence"):
            overview_sources.extend(evidence_values(item))
    if profile.get("evidence"):
        overview_sources.extend(evidence_values(profile))
    for reference in global_references:
        overview_sources.extend(reference_project_sources(reference_root, reference, evidence_values(reference)))
    overview_sources = list(dict.fromkeys(overview_sources))
    index = {
        "schema_version": SCHEMA_VERSION,
        "project_id": context["project_id"],
        "generated_at": utc_now(),
        "items": [
            {
                "id": "overview", "layer": "L1", "kind": "overview", "path": "overview.md",
                "sources": overview_sources,
                "source_fingerprints": context_source_fingerprints(context, overview_sources),
                "content_fingerprint": file_fingerprint([wiki / "overview.md"], wiki),
                "generated_by": "project-profile", "updated_at": utc_now(),
            },
            *index_items,
        ],
    }
    atomic_write_json(wiki / "index.json", index)
    return {
        "analysis_status": profile.get("analysis_status"),
        "modules": len(modules),
        "systems": len(systems),
        "bridges": len(profile.get("bridges", [])),
        "reference_projects": len(reference_projects),
    }

def render_architecture_system(
    skill_root: Path,
    context: dict[str, Any],
    architecture: dict[str, Any],
) -> bool:
    meaningful = any(architecture.get(key) for key in (
        "layers", "dependencies", "components", "circular_dependencies", "key_interfaces", "code_paths", "error_patterns",
    ))
    wiki = skill_root / "references" / "project_wiki"
    target = wiki / "systems" / "architecture.md"
    index_path = wiki / "index.json"
    index = read_json(index_path, {"schema_version": SCHEMA_VERSION, "items": []})
    index["items"] = [item for item in index.get("items", []) if item.get("id") != "architecture"]
    if not meaningful:
        target.unlink(missing_ok=True)
        atomic_write_json(index_path, index)
        return False

    evidence = list(dict.fromkeys([
        *architecture.get("evidence", []),
        *(
            value
            for key in ("layers", "dependencies", "components", "circular_dependencies", "key_interfaces", "code_paths")
            for item in architecture.get(key, [])
            for value in item.get("evidence", [])
        ),
    ]))
    lines = [
        "# Architecture Map", "",
        "This is an evidence-backed navigation map. Canonical project documents and source remain authoritative.", "",
        "## Layers", "",
        "| Level | Packages/Modules | Responsibility | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for layer in architecture.get("layers", []):
        layer_evidence = layer.get("evidence", evidence) if isinstance(layer, dict) else evidence
        lines.append(
            f"| {layer.get('level', '')} | {', '.join(layer.get('packages', []))} | "
            f"{layer.get('description', '')} | {', '.join(f'`{item}`' for item in layer_evidence)} |"
        )
    lines.extend(["", "## Package And Module Dependencies", ""])
    lines.extend(mermaid_dependency_graph(architecture.get("dependencies", [])) or ["No evidenced dependency edge recorded."])
    lines.extend(["", "## Interface Implementations", ""])
    lines.extend(mermaid_interface_graph(architecture.get("key_interfaces", [])) or ["No evidenced interface implementation recorded."])
    lines.extend(["", "## Key Interfaces", ""])
    lines.extend(markdown_items(architecture.get("key_interfaces", []), "No key interface recorded."))
    lines.extend(["", "## Critical Code Paths", ""])
    lines.extend(markdown_items(architecture.get("code_paths", []), "No critical code path recorded."))
    for code_path in architecture.get("code_paths", []):
        diagram = mermaid_sequence(code_path)
        if diagram:
            lines.extend(["", f"### {code_path.get('name', 'Flow')}", "", *diagram])
    lines.extend(["", "## Dependency Findings", ""])
    lines.extend(markdown_items(architecture.get("circular_dependencies", []), "No dependency cycle recorded."))
    lines.extend(["", "## Error Handling", ""])
    lines.extend(markdown_items([
        f"{key}: {value}" for key, value in architecture.get("error_patterns", {}).items()
    ], "No error-handling pattern recorded."))
    lines.extend(["", "## Evidence", "", *[f"- `{item}`" for item in evidence]])
    atomic_write_text(target, "\n".join(lines))
    index["items"].append({
        "id": "architecture", "layer": "L2", "kind": "system", "path": "systems/architecture.md",
        "sources": evidence, "source_fingerprints": context_source_fingerprints(context, evidence),
        "content_fingerprint": file_fingerprint([target], wiki),
        "generated_by": "architecture-analysis", "updated_at": utc_now(),
    })
    atomic_write_json(index_path, index)
    return True

def allowed_artifact_target(relative: str) -> bool:
    if relative == "SKILL.md":
        return True
    if relative == "references/rules/red_lines.yaml":
        return True
    directory_prefixes = (
        "references/workflows/",
        "references/bootstrap/",
        "scripts/checks/",
        "scripts/helpers/",
        "assets/templates/",
    )
    return any(relative.startswith(prefix) for prefix in directory_prefixes)

def artifact_validation_command(skill_root: Path, declaration: str) -> list[str]:
    try:
        parts = shlex.split(declaration, posix=os.name != "nt")
    except ValueError as exc:
        raise HarnessError(f"Invalid artifact validation declaration: {declaration}") from exc
    if not parts:
        raise HarnessError("Artifact validation declaration must not be empty.")
    executable = parts[0].lower()
    if executable in {"python", "python3"}:
        if len(parts) < 2 or parts[1].startswith("-"):
            raise HarnessError("Python artifact validation must name a project Harness script.")
        relative = safe_relative(parts[1], "artifact validation script")
        script = (skill_root / relative).resolve()
        if not is_within(script, skill_root) or not script.is_file():
            raise HarnessError(f"Artifact validation script does not exist: {relative}")
        return [str(Path(sys.executable).resolve()), str(script), *parts[2:]]
    if executable == "node":
        if len(parts) < 2 or parts[1].startswith("-"):
            raise HarnessError("Node artifact validation must name a project Harness script.")
        relative = safe_relative(parts[1], "artifact validation script")
        script = (skill_root / relative).resolve()
        if not is_within(script, skill_root) or not script.is_file():
            raise HarnessError(f"Artifact validation script does not exist: {relative}")
        node = shutil.which("node")
        if not node:
            raise HarnessError("Node artifact validation was declared but Node.js is unavailable.")
        return [node, str(script), *parts[2:]]
    if executable in {"powershell", "pwsh"}:
        lowered = [part.lower() for part in parts]
        if any(value in {"-command", "-encodedcommand", "-c", "-e"} for value in lowered[1:]):
            raise HarnessError("PowerShell artifact validation cannot use command or encoded-command mode.")
        if "-file" not in lowered:
            raise HarnessError("PowerShell artifact validation must use -File with a project Harness script.")
        index = lowered.index("-file")
        if index + 1 >= len(parts):
            raise HarnessError("PowerShell artifact validation has no -File target.")
        relative = safe_relative(parts[index + 1], "artifact validation script")
        script = (skill_root / relative).resolve()
        if not is_within(script, skill_root) or not script.is_file():
            raise HarnessError(f"Artifact validation script does not exist: {relative}")
        host = shutil.which(parts[0])
        if not host:
            raise HarnessError(f"Artifact validation host is unavailable: {parts[0]}")
        return [host, *parts[1:index + 1], str(script), *parts[index + 2:]]
    raise HarnessError(
        "Artifact validation must use a bounded Python, Node.js, or PowerShell script declaration."
    )

def run_artifact_validations(
    skill_root: Path,
    artifacts: list[dict[str, Any]],
    allow_executable_artifacts: bool,
) -> list[dict[str, Any]]:
    executable = [
        item for item in artifacts
        if item.get("validation") not in {"text-present", "workflow-contract", "rule-source"}
    ]
    if executable and not allow_executable_artifacts:
        raise HarnessError(
            "Analysis bundle contains executable artifact validations. Review the accepted delta and rerun with "
            "--allow-executable-artifacts only after explicit user authorization."
        )
    results = []
    for artifact in artifacts:
        declaration = artifact["validation"].strip()
        target = skill_root / artifact["path"]
        if declaration == "text-present":
            if not target.is_file() or not target.read_text(encoding="utf-8").strip():
                raise HarnessError(f"Text artifact is empty: {artifact['path']}")
            results.append({"path": artifact["path"], "declaration": declaration, "exit_code": 0})
            continue
        if declaration == "workflow-contract":
            stage = Path(artifact["path"]).stem
            command = [
                sys.executable, str(skill_root / "scripts" / "check_stage_artifacts.py"),
                "--skill-root", str(skill_root), "--stage", stage,
            ]
        elif declaration == "rule-source":
            command = [
                sys.executable, str(skill_root / "scripts" / "generate_rule_docs.py"),
                "--source", str(target), "--output-root", str(skill_root / "references" / "rules"),
            ]
        else:
            command = artifact_validation_command(skill_root, declaration)
        result = run(command, cwd=skill_root, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise HarnessError(
                f"Artifact validation failed for {artifact['path']}: {declaration}\n{detail}"
            )
        results.append({
            "path": artifact["path"],
            "declaration": declaration,
            "exit_code": result.returncode,
        })
    return results

def apply_creation_delta(
    skill_root: Path,
    bundle: Path | None,
    delta: dict[str, Any],
    context: dict[str, Any],
    allow_executable_artifacts: bool = False,
) -> dict[str, Any]:
    applied: list[str] = []
    skipped: list[dict[str, str]] = []
    validated_artifacts: list[dict[str, Any]] = []
    for artifact in delta.get("artifacts", []):
        if not isinstance(artifact, dict):
            raise HarnessError("Each creation-delta artifact must be an object.")
        action = artifact.get("action")
        target_relative = safe_relative(str(artifact.get("path", "")), "artifact target")
        if "capability_profile" in artifact:
            raise HarnessError(
                f"Artifact {target_relative} uses obsolete capability_profile metadata. "
                "Use evidence, owner, validation, and an allowed project Harness path."
            )
        if action in {"retain", "archive-only"}:
            skipped.append({"path": target_relative, "action": action})
            continue
        if action not in {"create", "replace", "merge"}:
            raise HarnessError(f"Unsupported creation-delta action: {action}")
        if not allowed_artifact_target(target_relative):
            raise HarnessError(f"Creation delta cannot write outside project Harness semantic owners: {target_relative}")
        if bundle is None:
            raise HarnessError("Bootstrap creation delta cannot install semantic artifacts.")
        for field in ("owner", "validation"):
            if not isinstance(artifact.get(field), str) or not artifact[field].strip():
                raise HarnessError(f"Artifact {target_relative} requires {field}.")
        evidence = evidence_values(artifact)
        validate_project_evidence(context["project_root"], evidence, f"artifact {target_relative}")
        source_relative = safe_relative(str(artifact.get("source", "")), "artifact source")
        source = (bundle / source_relative).resolve()
        if not is_within(source, bundle) or not source.is_file() or source.is_symlink():
            raise HarnessError(f"Artifact source is missing, outside the bundle, or a symlink: {source_relative}")
        target = skill_root / target_relative
        if action == "create" and target.exists():
            raise HarnessError(f"Creation delta create target already exists: {target_relative}")
        if action in {"replace", "merge"} and not target.exists():
            raise HarnessError(f"Creation delta {action} target does not exist: {target_relative}")
        if target.suffix.lower() not in TEXT_SUFFIXES and target.name != "red_lines.yaml":
            raise HarnessError(f"Only text project Harness artifacts are supported: {target_relative}")
        content = source.read_text(encoding="utf-8")
        atomic_write_text(target, content)
        applied.append(target_relative)
        artifact["evidence"] = evidence
        validated_artifacts.append(artifact)
    validations = run_artifact_validations(
        skill_root,
        validated_artifacts,
        allow_executable_artifacts,
    )
    return {
        "applied": applied,
        "skipped": skipped,
        "validations": validations,
        "merge_semantics": "full-candidate replacement",
    }

def persist_analysis(
    skill_root: Path,
    profile: dict[str, Any],
    audit: dict[str, Any],
    delta: dict[str, Any],
    architecture: dict[str, Any],
) -> None:
    analysis = skill_root / "state" / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)
    atomic_write_json(analysis / "project-profile.json", profile)
    atomic_write_json(analysis / "audit.json", audit)
    atomic_write_json(analysis / "creation-delta.json", delta)
    atomic_write_json(analysis / "architecture.json", architecture)

def generate_rule_views(skill_root: Path) -> dict[str, Any]:
    script = skill_root / "scripts" / "generate_rule_docs.py"
    source = skill_root / "references" / "rules" / "red_lines.yaml"
    output = skill_root / "references" / "rules"
    result = run(
        [sys.executable, str(script), "--source", str(source), "--output-root", str(output)],
        check=False,
    )
    if result.returncode != 0:
        raise HarnessError(f"Rule view generation failed: {(result.stderr or result.stdout).strip()}")
    value = json.loads(result.stdout)
    if not value.get("ok"):
        raise HarnessError(f"Rule view generation failed: {value}")
    return value

def validate_workflow_templates(skill_root: Path) -> None:
    script = skill_root / "scripts" / "check_stage_artifacts.py"
    for stage in ("intake", "locate", "plan", "implement", "verify", "close", "integrate", "evolve", "bootstrap-project"):
        result = run(
            [sys.executable, str(script), "--skill-root", str(skill_root), "--stage", stage],
            check=False,
        )
        if result.returncode != 0:
            raise HarnessError(f"Invalid generated {stage} workflow: {(result.stderr or result.stdout).strip()}")

def install_analysis_bundle(
    skill_root: Path,
    context: dict[str, Any],
    profile: dict[str, Any],
    audit: dict[str, Any],
    delta: dict[str, Any],
    architecture: dict[str, Any],
    bundle: Path | None,
    allow_executable_artifacts: bool = False,
) -> dict[str, Any]:
    knowledge = render_project_wiki(skill_root, context, profile, architecture)
    knowledge["architecture"] = render_architecture_system(skill_root, context, architecture)
    artifacts = apply_creation_delta(
        skill_root,
        bundle,
        delta,
        context,
        allow_executable_artifacts,
    )
    rules = generate_rule_views(skill_root)
    validate_workflow_templates(skill_root)
    persist_analysis(skill_root, profile, audit, delta, architecture)
    return {"knowledge": knowledge, "artifacts": artifacts, "rules": rules}
