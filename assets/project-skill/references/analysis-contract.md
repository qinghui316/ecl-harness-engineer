# Project Rescan And Analysis Contract

Use this contract during read-only audit, focused knowledge publication, and accepted E1 Evolution.
Focused migrate/E1 updates Agent-owned project documents, rules, workflows, templates, checks,
helpers, or the project Harness route through `creation-delta.json` without rebuilding
renderer-owned current facts. Agent judgment analyzes project
semantics; `scripts/harness_cli.py` validates and publishes deterministic artifacts.

## Evidence Funnel

Read repository prose as candidate context, then verify durable claims against manifests and
workspaces, CI/task files, entrypoints, imports/interfaces, configuration access, accepted
contracts, and tests. Select adapters from manifests
and source evidence. A top-level directory is not a module, an adapter default is not a configured
command, and search similarity is not an L3 fact.

Never read or persist secret values. Local evidence is a project-relative existing path. External
evidence may use `https:`, `user:`, `contract:`, or `registry:` identifiers.

## Focused Evolution Bundle

When accumulated evidence changes Agent-owned documents or Harness behavior without requiring a
whole-project semantic rescan, create only:

```text
creation-delta.json             # mode: evolution-focused
artifacts/                      # only sources named by creation-delta
```

Focused artifacts may create, replace, merge, or retire Agent-owned Markdown below
`references/project_wiki/**`, other references, routes, rules, workflows, templates, checks, and
helpers. Agent-owned Wiki pages declare ECL frontmatter with id, semantic layer, kind, status,
Owner, modules, evidence, and `managed_by: agent`. Retirement declares `validation: retired`.
Generated overview/catalog/index, derived rule views, local state, and Runtime remain protected.
A focused bundle does not run the evidence extractor or a full source-fingerprint scan.

## Four-File Full Refresh Bundle

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
semantic completion, score the audit, or authorize artifacts. Agent judgment reviews implementation
evidence and writes the final four files. The generated CLI remains only the
schema/evidence/publication gate.

Fixed byte, line, word, item, diagram, or command counts must not reject otherwise valid project
knowledge. Keep L1 navigable by moving implementation detail into linked L2/L3 pages, not by
truncating project-level owners, flows, commands, boundaries, or material unknowns.

All files use `schema_version: "1.0"`.

`project-profile.json` declares `analysis_status` as `complete`, `partial`, or `bootstrap_only` and
contains purpose, primary_flows, languages, frameworks, package_managers, source_roots,
entrypoints, modules, commands, environment, ci, bridges, reference_projects,
global_boundaries, unknowns,
and top-level evidence. Complete records require non-empty evidence. Commands use only
`configured|candidate|executed`. Environment contains services, startup_order, readiness,
migration/seed, cleanup, variable names/sensitivity, modes, helpers, unknowns, and evidence.
Each global boundary contains a non-empty `rule` and project evidence. `name` plus an optional
`description` is accepted for an existing bundle, but evidence without displayable boundary
semantics is invalid.
Every flow, environment mode/helper/object startup step, architecture component, dependency cycle,
interface, and code path must likewise contain the semantic fields used by its Wiki projection;
evidence-only objects are invalid.

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
code_paths, error_patterns, and evidence. It expresses verified architecture directly and does not
depend on repository prose documents.

A deterministic draft may contain `document_candidates` for Agent review. Remove that field before
semantic completion. A complete bundle must not contain `documents` or persist README, `docs/**`,
or ADR paths in profile, architecture, audit, or creation delta.

`audit.json` uses the dimensions, weights, score range, and overall calculation in
`references/audit-rubric.json`. Every gap has priority, dimension, issue, fix, and non-empty
evidence. `knowledge_findings` classifies every current drift/entropy finding with type, decision,
owner, projection, repair, and validation. Entropy findings also require an `entropy_report` with
measurable and owned `before` and `after` objects.

`creation-delta.json` contains mode, decisions, and artifacts. Decisions use
retain/move/merge/retire/archive-only/create with source, owner, projection, and validation.
Artifacts require path, create/replace/merge action, bundle-relative source, owner, validation, and
non-empty evidence. UTF-8 references and assets are open semantic owners; scripts remain limited to
checks/helpers and require explicit executable authorization. Project Wiki document evidence and
Owner must match its frontmatter. Runtime, state, generated Wiki views, and derived rule views are
protected.

## Publication Gate

`evolve stage` validates either bundle shape directly; a separate `project audit` is optional
diagnosis, not a staging prerequisite. The candidate must preserve the audit rubric and live
Change/INDEX/Registry state, pass rule/Wiki/stage checks and project validation, bind an independent
judge report to its fingerprint, score at least 80, and have no hard issue. Unavailable review is
`noop`; there is no E2.
