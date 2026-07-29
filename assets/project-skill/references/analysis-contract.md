# Project Rescan And Analysis Contract

Use this contract during read-only audit and accepted E1 Evolution. Agent judgment analyzes project
semantics; `scripts/harness_cli.py` validates and publishes deterministic artifacts.

## Evidence Funnel

Read canonical README/product/architecture/API documents, manifests and workspaces, CI/task files,
entrypoints, imports/interfaces, configuration access, and tests. Select adapters from manifests
and source evidence. A top-level directory is not a module, an adapter default is not a configured
command, and search similarity is not an L3 fact.

Never read or persist secret values. Local evidence is a project-relative existing path. External
evidence may use `https:`, `user:`, `contract:`, or `registry:` identifiers.

## Four-File Bundle

Create one directory containing:

```text
project-profile.json
architecture.json
audit.json
creation-delta.json
artifacts/                    # only sources named by creation-delta
```

Start with `python scripts/build_analysis_bundle.py --project-root <canonical-root> --output
<empty-bundle-dir>`. The extractor always emits `partial` or `bootstrap_only`; it cannot certify
semantic completion, score the audit, or authorize artifacts. Agent judgment reviews canonical
evidence and writes the final four files. The generated CLI remains only the
schema/evidence/publication gate.

Fixed byte, line, word, item, diagram, or command counts must not reject otherwise valid project
knowledge. Keep L1 navigable by moving implementation detail into linked L2/L3 pages, not by
truncating project-level owners, flows, commands, documents, boundaries, or material unknowns.

All files use `schema_version: "1.0"`.

`project-profile.json` declares `analysis_status` as `complete`, `partial`, or `bootstrap_only` and
contains purpose, primary_flows, languages, frameworks, package_managers, source_roots,
entrypoints, modules, commands, environment, documents, ci, bridges, reference_projects,
global_boundaries, unknowns,
and top-level evidence. Complete records require non-empty evidence. Commands use only
`configured|candidate|executed`. Environment contains services, startup_order, readiness,
migration/seed, cleanup, variable names/sensitivity, modes, helpers, unknowns, and evidence.

Each module has a stable id, name, responsibility, roots, entrypoints, interfaces, dependencies,
tests, commands, boundaries, and evidence. Each bridge has a purpose and non-empty mappings from a
proven term/API/schema/event/config/UI/CLI concept to its implementation owner, with evidence per
mapping.

Optional `reference_projects` records an isolated project-local checkout, source, inspected commit,
purpose, applicable problems, inspected files, source modules, license evidence, unknowns, and
reference-relative evidence. Target modules record accepted relationships in `reference_sources`;
L3 mappings may cite a reference project while retaining target evidence. Reference source facts
never populate target modules, commands, environment, CI, or dependencies.

`architecture.json` contains analysis_status, layers, circular_dependencies, key_interfaces,
code_paths, error_patterns, and evidence. It summarizes analyzed structure; canonical architecture
documents remain in the repository and are cited rather than copied.

`audit.json` uses the dimensions, weights, score range, and overall calculation in
`references/audit-rubric.json`. Every gap has priority, dimension, issue, fix, and non-empty
evidence. `knowledge_findings` classifies every current drift/entropy finding with type, decision,
owner, projection, repair, and validation. Entropy findings also require an `entropy_report` with
measurable and owned `before` and `after` objects.

`creation-delta.json` contains mode, decisions, and artifacts. Decisions use
retain/move/merge/retire/archive-only/create with source, owner, projection, and validation.
Artifacts require path, create/replace/merge action, bundle-relative source, owner, validation, and
non-empty evidence. Targets are limited to project Harness workflows, selected bootstrap reference,
rules, checks, helpers, and templates. Executables require explicit authorization.

## Publication Gate

Run `project audit --analysis-bundle <bundle>` before E1 staging. The candidate must preserve the
audit rubric and live
Change/INDEX/Registry state, pass rule/Wiki/stage checks and project validation, bind an independent
judge report to its fingerprint, score at least 80, and have no hard issue. Unavailable review is
`noop`; there is no E2.
