"""Read-only knowledge drift, link, citation, and entropy checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .core import HarnessError, atomic_write_json, atomic_write_text, canonical_id, file_fingerprint, git, git_value, is_within, read_json, reject_linked_ancestors, safe_relative, utc_now
from .project import primary_worktree_root, project_context, require_skill
from .transactions import guard_project_skill_read_only

NON_LOCAL_EVIDENCE_PREFIXES = ("http://", "https://", "user:", "contract:", "registry:")
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FINGERPRINT_FINDING_TYPES = {
    "changed": "knowledge_drift",
    "knowledge_drift": "knowledge_drift",
    "missing": "missing_knowledge_source",
    "missing_knowledge_source": "missing_knowledge_source",
    "invalid_source": "invalid_knowledge_source",
    "invalid_knowledge_source": "invalid_knowledge_source",
    "outside_project": "external_knowledge_source",
    "external_knowledge_source": "external_knowledge_source",
    "invalid_fingerprint": "invalid_knowledge_fingerprint",
    "invalid_knowledge_fingerprint": "invalid_knowledge_fingerprint",
}

AGENT_KNOWLEDGE_LAYERS = {"L1", "L2", "L3"}
AGENT_KNOWLEDGE_KINDS = {"current", "target", "decision", "guide"}
AGENT_KNOWLEDGE_STATUSES = {"proposed", "accepted", "in_progress", "implemented", "retired"}
GENERATED_KNOWLEDGE_PATHS = {"catalog.md"}
KNOWLEDGE_BASELINE_FILE = ".ecl-baselines.json"
LEGACY_KNOWLEDGE_INDEX_FILE = "index.json"
KNOWLEDGE_DOCUMENT_SUFFIXES = {".md", ".json", ".yaml", ".yml"}


def canonical_knowledge_finding_type(value: Any) -> str:
    text = str(value or "").strip()
    return FINGERPRINT_FINDING_TYPES.get(text, text)

def knowledge_source_location(context: dict[str, Any], source: str) -> tuple[Path, Path]:
    if source.startswith(".agents/reference-projects/"):
        parts = Path(source).parts
        if len(parts) < 4:
            return primary_worktree_root(context) / source, primary_worktree_root(context)
        primary = primary_worktree_root(context)
        base = primary / Path(*parts[:3])
        return primary / source, base
    else:
        base = context["project_root"]
    return base / source, base


def source_fingerprint(path: Path, source_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = source_root.resolve()
    if not is_within(resolved_path, resolved_root):
        raise HarnessError(f"Knowledge source resolves outside its evidence root: {path}")

    git_root_value = git_value(resolved_path.parent, "rev-parse", "--show-toplevel")
    if git_root_value:
        git_root = Path(git_root_value).resolve()
        if is_within(resolved_path, git_root):
            relative = resolved_path.relative_to(git_root).as_posix()
            tracked = git(git_root, "ls-files", "--error-unmatch", "--", relative, check=False)
            if tracked.returncode == 0:
                hashed = git(
                    git_root, "hash-object", f"--path={relative}", str(resolved_path), check=False,
                )
                blob = hashed.stdout.strip()
                if hashed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", blob):
                    payload = relative.encode("utf-8") + b"\0git:" + blob.encode("ascii")
                    return hashlib.sha256(payload).hexdigest()

    return _content_fingerprint(resolved_path, resolved_root)


def _content_fingerprint(path: Path, source_root: Path) -> str:
    relative = path.resolve().relative_to(source_root.resolve()).as_posix()
    content = path.read_bytes()
    if b"\0" not in content[:8192]:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            content = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(relative.encode("utf-8") + b"\0" + content).hexdigest()


class SourceFingerprintSnapshot:
    """Command-scoped source identities, batched by evidence Git root."""

    def __init__(self, context: dict[str, Any]):
        self.context = context
        self._results: dict[str, tuple[str, str | None]] = {}
        self._git_roots: dict[Path, Path | None] = {}

    def _git_root(self, source_root: Path) -> Path | None:
        resolved = source_root.resolve()
        if resolved not in self._git_roots:
            value = git_value(resolved, "rev-parse", "--show-toplevel")
            root = Path(value).resolve() if value else None
            self._git_roots[resolved] = root if root and is_within(resolved, root) else None
        return self._git_roots[resolved]

    @staticmethod
    def _chunks(values: list[str], size: int = 50) -> list[list[str]]:
        return [values[index:index + size] for index in range(0, len(values), size)]

    def _prime_git_group(
        self,
        git_root: Path,
        records: list[tuple[str, Path, Path, str]],
    ) -> None:
        relatives = [relative for _, _, _, relative in records]
        index_blobs: dict[str, str] = {}
        dirty: set[str] = set()
        bulk_ok = True
        for chunk in self._chunks(relatives):
            listed = git(git_root, "ls-files", "--stage", "-z", "--", *chunk, check=False)
            changed = git(git_root, "diff-files", "--name-only", "-z", "--", *chunk, check=False)
            if listed.returncode != 0 or changed.returncode != 0:
                bulk_ok = False
                break
            for entry in listed.stdout.split("\0"):
                if not entry or "\t" not in entry:
                    continue
                metadata, path = entry.split("\t", 1)
                fields = metadata.split()
                if len(fields) == 3 and fields[2] == "0" and re.fullmatch(r"[0-9a-f]{40,64}", fields[1]):
                    index_blobs[path] = fields[1]
            dirty.update(path for path in changed.stdout.split("\0") if path)

        for source, path, source_root, relative in records:
            if bulk_ok and relative in index_blobs and relative not in dirty:
                payload = relative.encode("utf-8") + b"\0git:" + index_blobs[relative].encode("ascii")
                self._results[source] = ("current", hashlib.sha256(payload).hexdigest())
                continue
            if bulk_ok and relative in index_blobs:
                hashed = git(
                    git_root, "hash-object", f"--path={relative}", str(path.resolve()), check=False,
                )
                blob = hashed.stdout.strip()
                if hashed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", blob):
                    payload = relative.encode("utf-8") + b"\0git:" + blob.encode("ascii")
                    self._results[source] = ("current", hashlib.sha256(payload).hexdigest())
                    continue
            fingerprint = (
                _content_fingerprint(path, source_root)
                if bulk_ok
                else source_fingerprint(path, source_root)
            )
            self._results[source] = ("current", fingerprint)

    def prime(self, sources: list[str] | set[str] | tuple[str, ...]) -> None:
        groups: dict[Path, list[tuple[str, Path, Path, str]]] = {}
        pending_content: list[tuple[str, Path, Path]] = []
        for raw_source in dict.fromkeys(sources):
            if not isinstance(raw_source, str) or raw_source.startswith(NON_LOCAL_EVIDENCE_PREFIXES):
                continue
            source = safe_relative(raw_source, "knowledge fingerprint source")
            if source in self._results:
                continue
            source_path, source_root = knowledge_source_location(self.context, source)
            resolved_root = source_root.resolve()
            resolved_source = source_path.resolve()
            if not is_within(resolved_source, resolved_root):
                self._results[source] = ("outside_project", None)
                continue
            if not source_path.is_file():
                self._results[source] = ("missing", None)
                continue
            git_root = self._git_root(source_root)
            if git_root and is_within(resolved_source, git_root):
                relative = resolved_source.relative_to(git_root).as_posix()
                groups.setdefault(git_root, []).append((source, source_path, source_root, relative))
            else:
                pending_content.append((source, source_path, source_root))

        for git_root, records in groups.items():
            self._prime_git_group(git_root, records)
        for source, path, source_root in pending_content:
            self._results[source] = ("current", _content_fingerprint(path, source_root))

    def result(self, source: str) -> tuple[str, str | None]:
        normalized = safe_relative(source, "knowledge fingerprint source")
        self.prime([normalized])
        return self._results[normalized]

    def local_sources(self) -> list[str]:
        return sorted(self._results)

    def digest(self, sources: list[str] | None = None) -> str:
        selected = sorted(dict.fromkeys(sources or self.local_sources()))
        self.prime(selected)
        payload = [
            [source, self._results[source][0], self._results[source][1]]
            for source in selected
        ]
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def context_source_fingerprints(
    context: dict[str, Any],
    sources: list[str],
    snapshot: SourceFingerprintSnapshot | None = None,
) -> dict[str, str]:
    active = snapshot or SourceFingerprintSnapshot(context)
    local_sources = [
        safe_relative(source, "knowledge fingerprint source")
        for source in sources
        if isinstance(source, str) and not source.startswith(NON_LOCAL_EVIDENCE_PREFIXES)
    ]
    active.prime(local_sources)
    result: dict[str, str] = {}
    for source in local_sources:
        status, fingerprint = active.result(source)
        if status == "current" and fingerprint:
            result[source] = fingerprint
    return result


def _frontmatter_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        if value[0] == '"':
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise HarnessError(f"Invalid quoted frontmatter value: {value}") from exc
            if not isinstance(parsed, str):
                raise HarnessError("Frontmatter scalar must decode to a string.")
            return parsed
        return value[1:-1].replace("''", "'")
    return value


def _frontmatter_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise HarnessError("Frontmatter array must use [item, item] or an indented list.")
    body = value[1:-1].strip()
    if not body:
        return []
    try:
        values = next(csv.reader([body], skipinitialspace=True))
    except csv.Error as exc:
        raise HarnessError(f"Invalid frontmatter array: {value}") from exc
    return [_frontmatter_scalar(item) for item in values]


def parse_agent_knowledge_frontmatter(path: Path) -> dict[str, Any] | None:
    """Parse the deliberately small ECL YAML subset used by Agent-owned Wiki pages."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise HarnessError(f"Knowledge frontmatter has no closing delimiter: {path}") from exc
    block = lines[1:end]
    try:
        start = next(index for index, line in enumerate(block) if line.strip() == "ecl:" and not line.startswith((" ", "\t")))
    except StopIteration:
        return None
    values: dict[str, Any] = {}
    active_list: str | None = None
    for raw in block[start + 1:]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("\t"):
            raise HarnessError(f"Knowledge frontmatter must use spaces, not tabs: {path}")
        if not raw.startswith(" "):
            break
        list_match = re.fullmatch(r"\s{4,}-\s+(.+)", raw)
        if list_match:
            if active_list is None:
                raise HarnessError(f"Knowledge frontmatter list has no owner field: {path}")
            values[active_list].append(_frontmatter_scalar(list_match.group(1)))
            continue
        field_match = re.fullmatch(r"\s{2}([a-z_]+):(?:\s*(.*))?", raw)
        if not field_match:
            raise HarnessError(f"Unsupported ECL knowledge frontmatter syntax: {path}: {raw.strip()}")
        key, raw_value = field_match.groups()
        if key in values:
            raise HarnessError(f"Duplicate ECL knowledge frontmatter field {key}: {path}")
        raw_value = raw_value or ""
        if not raw_value.strip():
            values[key] = []
            active_list = key
        elif raw_value.strip().startswith("["):
            values[key] = _frontmatter_list(raw_value)
            active_list = None
        else:
            values[key] = _frontmatter_scalar(raw_value)
            active_list = None
    allowed = {"id", "layer", "kind", "status", "owner", "modules", "evidence", "managed_by"}
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise HarnessError(f"Unsupported ECL knowledge frontmatter fields in {path}: {', '.join(unknown)}")
    required = ("id", "layer", "kind", "status", "owner", "evidence")
    missing = [key for key in required if key not in values]
    if missing:
        raise HarnessError(f"Agent-owned knowledge frontmatter is missing {', '.join(missing)}: {path}")
    identifier = values["id"]
    if not isinstance(identifier, str) or canonical_id(identifier, "Knowledge document id") != identifier:
        raise HarnessError(f"Knowledge document id must already be canonical: {identifier!r}")
    if values["layer"] not in AGENT_KNOWLEDGE_LAYERS:
        raise HarnessError(f"Knowledge layer must be L1, L2, or L3: {path}")
    if values["kind"] not in AGENT_KNOWLEDGE_KINDS:
        raise HarnessError(f"Knowledge kind must be current, target, decision, or guide: {path}")
    if values["status"] not in AGENT_KNOWLEDGE_STATUSES:
        raise HarnessError(f"Knowledge status is invalid: {path}")
    values.setdefault("managed_by", "agent")
    if values["managed_by"] not in {"agent", "renderer"}:
        raise HarnessError(f"Knowledge managed_by must be agent or renderer: {path}")
    if not isinstance(values["owner"], str) or not values["owner"].strip():
        raise HarnessError(f"Agent-owned knowledge requires a non-empty owner: {path}")
    for key in ("modules", "evidence"):
        values.setdefault(key, [])
        if not isinstance(values[key], list) or not all(isinstance(item, str) and item.strip() for item in values[key]):
            raise HarnessError(f"Knowledge frontmatter {key} must be a non-empty-string array: {path}")
        values[key] = list(dict.fromkeys(item.strip().replace("\\", "/") for item in values[key]))
    if not values["evidence"]:
        raise HarnessError(f"Agent-owned knowledge requires evidence: {path}")
    return values


def _frontmatter_lines(metadata: dict[str, Any]) -> list[str]:
    lines = ["---", "ecl:"]
    for key in ("id", "layer", "kind", "status", "owner"):
        lines.append(f"  {key}: {json.dumps(str(metadata[key]), ensure_ascii=False)}")
    for key in ("modules", "evidence"):
        values = metadata.get(key, [])
        if values:
            lines.append(f"  {key}:")
            lines.extend(f"    - {json.dumps(str(value), ensure_ascii=False)}" for value in values)
        else:
            lines.append(f"  {key}: []")
    if metadata.get("managed_by"):
        lines.append(f"  managed_by: {metadata['managed_by']}")
    return [*lines, "---", ""]


def ensure_renderer_knowledge_frontmatter(path: Path, item: dict[str, Any]) -> None:
    if parse_agent_knowledge_frontmatter(path) is not None:
        return
    raw_layer = str(item.get("layer", "L3"))
    layer = raw_layer if raw_layer in AGENT_KNOWLEDGE_LAYERS else ("L1" if raw_layer == "index" else "L3")
    identifier = canonical_id(str(item.get("id", path.stem)), "Knowledge document id")
    sources = [str(value) for value in item.get("sources", []) if str(value).strip()]
    if not sources:
        sources = [f"contract:analysis/{identifier}"]
    modules = [str(value) for value in item.get("modules", []) if str(value).strip()]
    if not modules and item.get("kind") == "module":
        modules = [identifier]
    metadata = {
        "id": identifier,
        "layer": layer,
        "kind": "current",
        "status": "implemented",
        "owner": str(item.get("owner") or item.get("generated_by") or identifier),
        "modules": modules,
        "evidence": sources,
        "managed_by": "renderer",
    }
    content = path.read_text(encoding="utf-8")
    atomic_write_text(path, "\n".join([*_frontmatter_lines(metadata), content]))


def convert_legacy_knowledge_index(
    skill_root: Path,
    context: dict[str, Any],
) -> dict[str, Any]:
    wiki = skill_root / "references" / "project_wiki"
    index_path = wiki / LEGACY_KNOWLEDGE_INDEX_FILE
    legacy = read_json(index_path, None)
    if not isinstance(legacy, dict) or not isinstance(legacy.get("items"), list):
        return {"converted": False, "documents": 0}
    legacy_by_id: dict[str, dict[str, Any]] = {}
    for raw_item in legacy["items"]:
        if not isinstance(raw_item, dict) or not raw_item.get("id") or not raw_item.get("path"):
            raise HarnessError("Legacy project knowledge index contains an invalid item.")
        identifier = str(raw_item["id"])
        if identifier in legacy_by_id:
            raise HarnessError(f"Legacy project knowledge index contains duplicate id: {identifier}")
        legacy_by_id[identifier] = raw_item
        path = wiki / safe_relative(str(raw_item["path"]), "legacy knowledge path")
        if not path.is_file() or path.suffix.lower() != ".md":
            raise HarnessError(f"Legacy project knowledge document is missing: {raw_item['path']}")
        if parse_agent_knowledge_frontmatter(path) is None:
            ensure_renderer_knowledge_frontmatter(path, raw_item)

    items = discover_project_knowledge(
        skill_root, context, include_content_fingerprint=True,
    )
    ids = [item["id"] for item in items]
    paths = [item["path"] for item in items]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise HarnessError("Converted project knowledge contains duplicate id or path.")
    documents: dict[str, Any] = {}
    snapshot = SourceFingerprintSnapshot(context)
    for item in items:
        old = legacy_by_id.get(item["id"], {})
        fingerprints = old.get("source_fingerprints")
        if not isinstance(fingerprints, dict):
            fingerprints = context_source_fingerprints(context, item["sources"], snapshot)
        documents[item["id"]] = {
            "path": item["path"],
            "content_fingerprint": item["content_fingerprint"],
            "source_fingerprints": fingerprints,
        }
    atomic_write_json(wiki / KNOWLEDGE_BASELINE_FILE, {
        "schema_version": "1.0",
        "project_id": context["project_id"],
        "documents": documents,
    })
    render_knowledge_catalog(skill_root, items)
    index_path.unlink()
    return {"converted": True, "documents": len(documents)}


def _markdown_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return path.stem.replace("-", " ").strip().title()


def discover_project_knowledge(
    skill_root: Path,
    context: dict[str, Any],
    snapshot: SourceFingerprintSnapshot | None = None,
    include_content_fingerprint: bool = False,
) -> list[dict[str, Any]]:
    wiki = skill_root / "references" / "project_wiki"
    items: list[dict[str, Any]] = []
    for path in (sorted(wiki.rglob("*.md")) if wiki.is_dir() else []):
        relative = path.relative_to(wiki).as_posix()
        if relative in GENERATED_KNOWLEDGE_PATHS:
            continue
        item = agent_knowledge_item(
            skill_root, context, path, snapshot,
            include_content_fingerprint=include_content_fingerprint,
        )
        if item is not None:
            items.append(item)
    return items


def discover_agent_knowledge(
    skill_root: Path,
    context: dict[str, Any],
    snapshot: SourceFingerprintSnapshot | None = None,
) -> list[dict[str, Any]]:
    return [
        item for item in discover_project_knowledge(skill_root, context, snapshot)
        if item.get("managed_by") == "agent"
    ]


def agent_knowledge_item(
    skill_root: Path,
    context: dict[str, Any],
    path: Path,
    snapshot: SourceFingerprintSnapshot | None = None,
    *,
    include_content_fingerprint: bool = True,
) -> dict[str, Any] | None:
    wiki = skill_root / "references" / "project_wiki"
    metadata = parse_agent_knowledge_frontmatter(path)
    if metadata is None:
        return None
    sources = metadata["evidence"]
    item = {
        "id": metadata["id"],
        "title": _markdown_title(path),
        "layer": metadata["layer"],
        "kind": metadata["kind"],
        "status": metadata["status"],
        "owner": metadata["owner"],
        "modules": metadata["modules"],
        "path": path.relative_to(wiki).as_posix(),
        "sources": sources,
        "managed_by": metadata["managed_by"],
        "updated_at": utc_now(),
    }
    if include_content_fingerprint:
        item["content_fingerprint"] = _content_fingerprint(path, wiki)
    return item


def _catalog_cell(value: Any) -> str:
    return str(value or "-").replace("|", "\\|").replace("\n", " ")


def render_knowledge_catalog(skill_root: Path, items: list[dict[str, Any]]) -> None:
    wiki = skill_root / "references" / "project_wiki"
    lines = [
        "# Project Knowledge Catalog", "",
        "Generated from project knowledge frontmatter. Select documents by layer, kind, module, and owner; do not edit this file.", "",
    ]
    layer_order = {"L1": 0, "L2": 1, "L3": 2, "reference": 3, "index": 4}
    for layer in sorted({str(item.get("layer", "other")) for item in items}, key=lambda value: (layer_order.get(value, 9), value)):
        lines.extend([
            f"## {layer}", "",
            "| Document | Kind | Status | Owner | Modules |", "| --- | --- | --- | --- | --- |",
        ])
        selected = sorted(
            (item for item in items if str(item.get("layer", "other")) == layer),
            key=lambda item: (str(item.get("kind", "")), str(item.get("status", "")), str(item.get("id", ""))),
        )
        for item in selected:
            modules = ", ".join(item.get("modules", [])) or "-"
            lines.append(
                f"| [{_catalog_cell(item.get('title') or item.get('id'))}]({_catalog_cell(item.get('path'))}) | "
                f"{_catalog_cell(item.get('kind'))} | {_catalog_cell(item.get('status'))} | "
                f"{_catalog_cell(item.get('owner'))} | {_catalog_cell(modules)} |"
            )
        lines.append("")
    atomic_write_text(wiki / "catalog.md", "\n".join(lines))


def rebuild_project_wiki_catalog(
    skill_root: Path,
    context: dict[str, Any],
    snapshot: SourceFingerprintSnapshot | None = None,
    refresh_all: bool = False,
) -> dict[str, Any]:
    wiki = skill_root / "references" / "project_wiki"
    baseline_path = wiki / KNOWLEDGE_BASELINE_FILE
    previous = read_json(baseline_path, {"documents": {}})
    previous_documents = previous.get("documents", {}) if isinstance(previous, dict) else {}
    if not isinstance(previous_documents, dict):
        previous_documents = {}
    items = discover_project_knowledge(
        skill_root, context, include_content_fingerprint=True,
    )
    ids = [item["id"] for item in items]
    paths = [item["path"] for item in items]
    if len(set(ids)) != len(ids):
        raise HarnessError("Project knowledge contains a duplicate id.")
    if len(set(paths)) != len(paths):
        raise HarnessError("Project knowledge contains a duplicate path.")

    active = snapshot or SourceFingerprintSnapshot(context)
    documents: dict[str, Any] = {}
    refreshed: list[str] = []
    for item in items:
        path = wiki / item["path"]
        if markdown_body_is_empty(path):
            raise HarnessError(f"Project knowledge must have a non-empty body: {item['path']}")
        link_findings = knowledge_link_findings(skill_root, path, item["id"])
        if link_findings:
            raise HarnessError(f"Project knowledge has invalid local links: {link_findings}")
        previous_item = previous_documents.get(item["id"], {})
        unchanged = not refresh_all and (
            isinstance(previous_item, dict)
            and previous_item.get("path") == item["path"]
            and previous_item.get("content_fingerprint") == item["content_fingerprint"]
            and isinstance(previous_item.get("source_fingerprints"), dict)
        )
        source_fingerprints = (
            previous_item["source_fingerprints"]
            if unchanged
            else context_source_fingerprints(context, item["sources"], active)
        )
        if not unchanged:
            refreshed.append(item["id"])
        documents[item["id"]] = {
            "path": item["path"],
            "content_fingerprint": item["content_fingerprint"],
            "source_fingerprints": source_fingerprints,
        }
    items.sort(key=lambda item: (item["layer"], item["kind"], item["id"]))
    baseline = {
        "schema_version": "1.0",
        "project_id": context["project_id"],
        "documents": documents,
    }
    atomic_write_json(baseline_path, baseline)
    render_knowledge_catalog(skill_root, items)
    return {"items": items, "documents": documents, "refreshed": refreshed}


def knowledge_fingerprint_scan(
    skill_root: Path,
    context: dict[str, Any],
    selected_sources: dict[str, set[str]] | None = None,
    snapshot: SourceFingerprintSnapshot | None = None,
) -> dict[str, Any]:
    wiki = skill_root / "references" / "project_wiki"
    baseline_path = wiki / KNOWLEDGE_BASELINE_FILE
    baseline = read_json(baseline_path, None)
    if not isinstance(baseline, dict) or not isinstance(baseline.get("documents"), dict):
        raise HarnessError(f"Invalid project knowledge baseline: {baseline_path}")

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    comparisons: list[tuple[Any, str, str]] = []
    checked = 0

    def add(finding_type: str, item_id: Any, source: Any, **detail: Any) -> None:
        key = (finding_type, str(item_id or ""), str(source or ""))
        if key in seen:
            return
        seen.add(key)
        findings.append({"type": finding_type, "item": item_id, "source": source, **detail})

    for item_id, item in baseline["documents"].items():
        if not isinstance(item, dict):
            add("invalid_source", item_id, None, detail="knowledge baseline item must be an object")
            continue
        selected_for_item = None if selected_sources is None else selected_sources.get(str(item_id or ""))
        if selected_sources is not None and selected_for_item is None:
            continue
        fingerprints = item.get("source_fingerprints", {})
        if not isinstance(fingerprints, dict):
            add("invalid_fingerprint", item_id, None, detail="source_fingerprints must be an object")
            continue
        for raw_source, expected in fingerprints.items():
            if not isinstance(raw_source, str) or not raw_source.strip():
                add("invalid_source", item_id, raw_source, detail="source must be a non-empty string")
                continue
            if raw_source.startswith(NON_LOCAL_EVIDENCE_PREFIXES):
                continue
            try:
                source = safe_relative(raw_source, "knowledge fingerprint source")
            except HarnessError as exc:
                add("invalid_source", item_id, raw_source, detail=str(exc))
                continue
            if selected_for_item is not None and source not in selected_for_item:
                continue
            if not isinstance(expected, str) or not FINGERPRINT_PATTERN.fullmatch(expected):
                add("invalid_fingerprint", item_id, source, expected=expected)
                continue
            checked += 1
            comparisons.append((item_id, source, expected))

    active = snapshot or SourceFingerprintSnapshot(context)
    active.prime([source for _, source, _ in comparisons])
    unique_sources = {source for _, source, _ in comparisons}
    for item_id, source, expected in comparisons:
            status, current = active.result(source)
            if status == "outside_project":
                add("outside_project", item_id, source, expected=expected)
            elif status == "missing":
                add("missing", item_id, source, expected=expected, current=None)
            elif current != expected:
                add("changed", item_id, source, expected=expected, current=current)

    return {
        "read_only": True,
        "healthy": not findings,
        "stale": bool(findings),
        "checked": checked,
        "unique_sources": len(unique_sources),
        "findings": findings,
    }

def markdown_body_is_empty(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
        except StopIteration:
            return True
        return not "\n".join(lines[end + 1:]).strip()
    return not text.strip()


def knowledge_link_findings(
    skill_root: Path,
    path: Path,
    item_id: Any = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    content = path.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)", content):
        if "://" in target or target.startswith("#"):
            continue
        unresolved = path.parent / target
        resolved = unresolved.resolve()
        if not is_within(resolved, skill_root):
            findings.append({"type": "external_knowledge_link", "id": item_id, "target": target})
            continue
        try:
            reject_linked_ancestors(skill_root, unresolved, "Knowledge link")
        except HarnessError as exc:
            findings.append({
                "type": "linked_knowledge_target", "id": item_id,
                "target": target, "detail": str(exc),
            })
        if not resolved.exists():
            findings.append({"type": "broken_knowledge_link", "id": item_id, "target": target})
    return findings

@guard_project_skill_read_only
def knowledge_scan(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    return knowledge_fingerprint_scan(skill_root, context)

def knowledge_check_internal(
    skill_root: Path,
    context: dict[str, Any],
    snapshot: SourceFingerprintSnapshot | None = None,
    include_fingerprints: bool = True,
) -> dict[str, Any]:
    knowledge = skill_root / "references" / "project_wiki"
    overview = knowledge / "overview.md"
    catalog = knowledge / "catalog.md"
    baseline = read_json(knowledge / KNOWLEDGE_BASELINE_FILE, {})
    baseline_documents = baseline.get("documents", {}) if isinstance(baseline, dict) else {}
    if not isinstance(baseline_documents, dict):
        baseline_documents = {}
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for path in sorted(knowledge.rglob("*.md")) if knowledge.is_dir() else []:
        relative = path.relative_to(knowledge).as_posix()
        if relative in GENERATED_KNOWLEDGE_PATHS:
            continue
        try:
            item = agent_knowledge_item(skill_root, context, path)
        except (HarnessError, UnicodeDecodeError) as exc:
            findings.append({
                "type": "invalid_knowledge_frontmatter", "path": relative, "detail": str(exc),
            })
            continue
        if item is None:
            findings.append({"type": "missing_knowledge_frontmatter", "path": relative})
            continue
        items.append(item)
    items_by_id = {item["id"]: item for item in items}
    try:
        fingerprint_scan = knowledge_fingerprint_scan(
            skill_root, context, snapshot=snapshot,
        ) if include_fingerprints else {
            "healthy": True, "stale": False, "checked": 0, "unique_sources": 0, "findings": [],
        }
    except HarnessError as exc:
        fingerprint_scan = {
            "healthy": False, "stale": False, "checked": 0, "unique_sources": 0, "findings": [],
        }
        findings.append({"type": "invalid_knowledge_baseline", "detail": str(exc)})
    for item in fingerprint_scan["findings"]:
        normalized = {
            **item,
            "type": canonical_knowledge_finding_type(item["type"]),
            "id": item.get("item"),
        }
        owner = items_by_id.get(str(item.get("item")), {})
        if normalized["type"] == "knowledge_drift" and owner.get("kind") in {"target", "decision"}:
            normalized["type"] = "knowledge_evidence_review"
            normalized["reason"] = "target or decision evidence changed and requires semantic review"
            warnings.append(normalized)
        else:
            findings.append(normalized)
    finding_keys = {
        (item.get("type"), item.get("id"), item.get("source"))
        for item in findings
    }
    if not overview.exists():
        findings.append({"type": "missing_l1", "path": str(overview)})
    if not catalog.exists():
        findings.append({"type": "missing_knowledge_catalog", "path": str(catalog)})
    ids: dict[str, list[str]] = {}
    paths_by_document: dict[str, list[str]] = {}
    for item in items:
        identifier = item["id"]
        relative_path = item["path"]
        ids.setdefault(identifier, []).append(relative_path)
        paths_by_document.setdefault(relative_path, []).append(identifier)
        path = knowledge / relative_path
        baseline_item = baseline_documents.get(identifier)
        if not isinstance(baseline_item, dict):
            findings.append({"type": "missing_knowledge_baseline", "id": identifier, "path": relative_path})
        elif (
            baseline_item.get("path") != relative_path
            or baseline_item.get("content_fingerprint") != item["content_fingerprint"]
        ):
            findings.append({"type": "knowledge_baseline_stale", "id": identifier, "path": relative_path})
        for source in item.get("sources", []):
            if not isinstance(source, str):
                findings.append({"type": "invalid_knowledge_source", "id": item.get("id")})
                continue
            if source.startswith(NON_LOCAL_EVIDENCE_PREFIXES):
                continue
            try:
                source = safe_relative(source, "knowledge source")
            except HarnessError as exc:
                findings.append({"type": "invalid_knowledge_source", "id": item.get("id"), "detail": str(exc)})
                continue
            source_path, source_root = knowledge_source_location(context, source)
            if not is_within(source_path.resolve(), source_root):
                key = ("external_knowledge_source", item.get("id"), source)
                if key not in finding_keys:
                    findings.append({"type": key[0], "id": key[1], "source": key[2]})
                    finding_keys.add(key)
            elif not source_path.exists():
                key = ("missing_knowledge_source", item.get("id"), source)
                if key not in finding_keys:
                    findings.append({"type": key[0], "id": key[1], "source": key[2]})
                    finding_keys.add(key)
        if path.exists() and path.suffix == ".md":
            findings.extend(knowledge_link_findings(skill_root, path, item.get("id")))
    for identifier, identifier_paths in ids.items():
        if not identifier or len(identifier_paths) > 1:
            findings.append({"type": "duplicate_knowledge_id", "id": identifier, "paths": identifier_paths})
    for relative, identifiers in paths_by_document.items():
        if len(identifiers) > 1:
            findings.append({"type": "duplicate_knowledge_path", "path": relative, "ids": identifiers})
    document_files = [
        path for path in knowledge.rglob("*")
        if path.is_file() and path.suffix.lower() in KNOWLEDGE_DOCUMENT_SUFFIXES
    ] if knowledge.is_dir() else []
    for path in document_files:
        relative = path.relative_to(knowledge).as_posix()
        excluded = {
            *GENERATED_KNOWLEDGE_PATHS,
            KNOWLEDGE_BASELINE_FILE,
            LEGACY_KNOWLEDGE_INDEX_FILE,
        }
        if relative not in excluded and relative not in paths_by_document:
            findings.append({"type": "orphan_knowledge_document", "path": relative})
        if path.suffix.lower() == ".md" and markdown_body_is_empty(path):
            findings.append({"type": "empty_knowledge_entry", "path": relative})
    repairs = {
        "broken_knowledge_link": "Repair the project-Wiki link or remove the unsupported projection through migrate/E1.",
        "knowledge_drift": "Rescan the affected source and replan against Registry/canonical facts before refreshing Wiki.",
        "orphan_knowledge_document": "Add valid frontmatter in the current Change or move the file outside project_wiki.",
        "knowledge_baseline_stale": "Run change reindex after reviewing the changed document and its evidence.",
        "missing_knowledge_baseline": "Run change reindex to create the document fingerprint baseline.",
        "knowledge_evidence_review": "Review changed target/decision evidence without treating it as implemented-code drift.",
    }
    for severity, severity_items in (("error", findings), ("warning", warnings)):
        for item in severity_items:
            item.setdefault("severity", severity)
            item.setdefault("owner", "project Harness knowledge/audit owner")
            item.setdefault("location", item.get("path") or item.get("id") or "project knowledge graph")
            item.setdefault("reason", item["type"].replace("_", " "))
            item.setdefault("repair", repairs.get(item["type"], "Review the evidence and repair the document in the current Change."))
    return {
        "read_only": True,
        "healthy": not findings,
        "stale": any(item.get("type") == "knowledge_drift" for item in findings),
        "checked": fingerprint_scan["checked"],
        "unique_sources": fingerprint_scan["unique_sources"],
        "findings": findings,
        "warnings": warnings,
        "items": len(items),
    }

@guard_project_skill_read_only
def knowledge_check(args: argparse.Namespace) -> dict[str, Any]:
    context = project_context(Path(args.project_root))
    skill_root = require_skill(context, args)
    return knowledge_check_internal(skill_root, context)
