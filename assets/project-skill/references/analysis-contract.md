# Project Audit And Full Refresh Contract

Use this contract during read-only semantic audit and full migration. Accepted E1 reads it only
when a complete project rescan is required. Ordinary project Harness documents are edited directly
inside a Structured Change; they do not use a migration bundle. Agent judgment analyzes project
semantics; `scripts/harness_cli.py` validates deterministic artifacts for a full project knowledge
refresh.

## Evidence Funnel

Read repository prose as candidate context, then verify durable claims against manifests and
workspaces, CI/task files, entrypoints, imports/interfaces, configuration access, accepted
contracts, and tests. Select adapters from manifests
and source evidence. A top-level directory is not a module, an adapter default is not a configured
command, and search similarity is not an L3 fact.

Never read or persist secret values. Local evidence is a project-relative existing path. External
evidence may use `https:`, `user:`, `contract:`, or `registry:` identifiers.

## Focused E1 Bundle

During accepted E1, when accumulated evidence changes project documents or Harness behavior without requiring a
whole-project semantic rescan, create only:

```text
creation-delta.json             # mode: evolution-focused
artifacts/                      # only sources named by creation-delta
```

Focused E1 artifacts may create, replace, merge, or retire agent-maintained Markdown below
`references/project_wiki/**`, other references, routes, rules, workflows, templates, checks, and
helpers. Agent-maintained Wiki pages declare ECL frontmatter with ID, semantic layer, kind, status,
knowledge owner, modules, evidence, and optional `managed_by: agent`. Retirement declares
`validation: retired`. The generated catalog, knowledge source baseline, derived rule views, local
state, and Runtime remain protected. A focused bundle does not run the evidence extractor or a full
source-fingerprint scan.

## Full Refresh Bundle

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
evidence and writes the four control files plus any artifact payloads declared by
`creation-delta.json`. The generated CLI only validates schema, evidence, and candidate acceptance
checks.

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
evidence. `knowledge_findings` records Agent-reviewed source changes or semantic findings with type,
decision, knowledge owner, projection, repair, and validation. The compatible `entropy_report` field
is an optional documentation-duplication report with measurable and assigned `before` and `after`
objects. Runtime does not infer duplication or stale-content findings from prose.

`creation-delta.json` contains mode, decisions, and artifacts. Decisions use
retain/move/merge/retire/archive-only/create with source, owner, projection, and validation.
Artifacts require path, create/replace/merge/retire action, owner, validation, and non-empty
evidence; create/replace/merge also require a bundle-relative source. Retirement is available only
while applying a staged candidate to an existing project Harness, targets an existing physical optional
artifact, and remains forbidden during init or bootstrap. UTF-8 references and assets are open
artifact classes; scripts remain limited to checks/helpers and require explicit executable
authorization. Project Wiki document evidence and knowledge owner must match its frontmatter.
Runtime, state, required workflows, required rule sources, generated Wiki views, and derived rule
views are protected.

## Candidate Acceptance Checks

`evolve stage` validates either bundle shape directly; a separate `project audit` is optional
diagnosis, not a staging prerequisite. The candidate must preserve the audit rubric and live
Change/INDEX/Registry state, pass rule/Wiki/stage checks and project validation, bind an independent
review report to its content digest, score at least 80, and have no blocking issue. Status `noop`
means review completed with no change applied; there is no E2.
