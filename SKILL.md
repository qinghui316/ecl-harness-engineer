---
name: ecl-harness-engineer
description: "Create, audit, or migrate a project-bound local Harness for reliable AI coding. Use when a project needs ECL Change planning, layered project knowledge, local Codex/Claude worktree coordination, PR-like Integration, Harness Evolution, greenfield guidance, or reference-source maps. Do not use for ordinary feature implementation."
---

# ECL Harness Engineer

Create one project Harness that gives local Codex and Claude agents the same project knowledge,
Change history, coordination facts, and operating rules. Its physical directory lives at
`<primary-worktree>/.agents/skills/<project-id>-harness/`, stays outside Git, and is linked from the
project-level Codex and Claude discovery directories in every local worktree.

Project semantics belong to Agent analysis. The Harness runtime handles schemas, paths, indexes,
links, coordination Registry records, commit identity, exclusive locks, and crash-recoverable
transactions.

A Change is one recorded and validated unit of work. The coordination Registry stores shared
worktree facts, and a Lane is one parallel work lane. E1 is the user approval checkpoint that
starts a periodic Harness review. I2 is the user approval to land an independently reviewed
Integration candidate. Both identifiers remain in commands and persisted state.

## Choose The Operation

| Operation | Use when | Result |
| --- | --- | --- |
| `init` | No project Harness exists | Create one from current evidence, or an honest bootstrap for an empty project |
| `audit` | The user asks what is missing, stale, unsafe, or inconsistent | Produce a read-only structural and semantic gap report |
| `migrate` | An existing project Harness needs an evidence-backed refresh or runtime/schema update | Apply a recoverable transaction while preserving live Change and coordination Registry state |

When responsibility is unclear, audit before proposing a change.

## Core Route

### 1. Inspect Read Only

Read `references/project-analysis-and-creation.md`. Resolve the project root, applicable
instructions, Git/common-dir/worktree facts, existing project Harness, repository-document
candidates, manifests, source roots, entrypoints, tests, CI, and command evidence. Treat repository
prose as a temporary analysis lead; verify durable knowledge against code, manifests, interfaces,
configuration, tests, accepted contracts, or explicit user evidence.

Use these roles without merging their responsibilities:

- `agents/analyzer.md`: purpose, flows, modules, architecture, boundaries, reference relationships.
- `agents/auditor.md`: evidence quality, gaps, duplication, source changes, and repair priorities.
- `agents/creator-docs.md`: project knowledge, workflows, Change templates, and compact routes.
- `agents/creator-config.md`: commands, environment, services, readiness, and helpers.
- `agents/creator-linters.md`: accepted project checks with actionable failures.

Select adapters from `references/adapters/` using manifests and source evidence. Record commands as
`configured`, `candidate`, or `executed`. Record variable names and sensitivity, never secret
values.

### 2. Produce The Agent-Reviewed Bundle

The migration analysis bundle contains:

```text
project-profile.json
architecture.json
audit.json
creation-delta.json
artifacts/
```

`scripts/build_analysis_bundle.py` may extract a `partial` or `bootstrap_only` evidence draft. It
cannot decide purpose, module responsibility, final audit scores, or final migration artifacts. The
Analyzer, Auditor, and Creators review implementation evidence and complete the bundle.

Read `references/knowledge-model.md` for L1/L2/L3 and reference-source maps,
`references/architecture-diagrams.md` for evidenced Mermaid projections, and
`references/workflow-contracts.md` for generated stage contracts.

### 3. Confirm Material Decisions

Ask only for information that cannot be discovered and changes project purpose, ownership,
safety, executable authorization, or command behavior. An empty project requires confirmed
purpose, stack, application type, constraints, and acceptance before business scaffolding.

### 4. Apply The Validated Update

`CHECKPOINT H1`: before `init` or `migrate`, show the resolved project root, stable project id or
new identity, semantic completion status, managed route/link changes, executable artifacts, and
validation plan. Apply the update only after the user confirms these material effects.

Use the public runtime rather than hand-writing identity, links, Registry state, or indexes:

```text
python <skill-dir>/scripts/harness_cli.py project init --project-root <path> --analysis-bundle <bundle>
python <skill-dir>/scripts/harness_cli.py project audit --project-root <path> [--analysis-bundle <bundle>]
python <skill-dir>/scripts/harness_cli.py project migrate --project-root <path> --analysis-bundle <bundle>
python <skill-dir>/scripts/harness_cli.py project doctor --project-root <path>
```

Without a complete bundle, `init` may only report `bootstrapped` and
`semantic_complete: false`. Non-Git projects use single-Lane mode. Git initialization is a user
decision.

For greenfield work, read `references/greenfield-templates.md`; use
`scripts/render_greenfield.py` only for the selected Go, TypeScript, or Python CLI/Web API after an
approved Structured Change. Business source, tests, project commands, Make/package scripts, and CI
remain normal Change outputs.

### 5. Verify And Hand Off

Apply `references/validation.md`. Verify structure, frontmatter, links, coordination Registry
identity, knowledge citations/indexes, rule views, stage contracts, project commands, and failure
recovery. Report the project Harness path, links, mode, recorded Git integration base, knowledge
produced, command evidence, unknowns, existing failures, and the next Change or repair action.

## Project Harness Contract

The project Harness owns:

- short `SKILL.md` routing and critical/stage rule views;
- L1 overview/catalog, current maps generated by full project analysis, and agent-maintained
  L1/L2/L3 current, target, decision, and guide documents;
- Change active/parking/archive evidence and generated `INDEX.json`;
- parallel work Lane, path, contract, Git integration base, Integration, and lock records;
- evidence and results for the periodic Harness review (E1), including recoverable transactions;
- project-specific workflows, templates, checks, environment guidance, and reference-source maps.

Every worktree reads the same physical directory. Compact managed blocks in `AGENTS.md` and
`CLAUDE.md` route agents to it; the tracked connector repairs discovery links for new worktrees.

When facts conflict, use the source that owns the question:

```text
coordination state -> Registry integration-base events and contracts
accepted work scope -> current Change spec, plan, and evidence
implemented behavior -> code, manifests, configuration, tests, and accepted interfaces
periodic project context -> L1/L2/L3 project knowledge
```

A related source change returns `refresh-needed` and requires replanning. Registry records do not
override implemented behavior or the accepted Change plan. An unrelated change to the recorded Git
integration base does not block a parallel work Lane.

## Behavior Routes

| Work | Read |
| --- | --- |
| ECL intake, plan, tasks, validation, close, archive, INDEX | `references/ecl-harness.md` |
| Environment, commands, services, readiness, variables | `references/environment-detection-guide.md`, `references/environment-config-guide.md` |
| L1/L2/L3, current/target/decision documents, catalog, citations, duplication/stale-content review, reference-source maps | `references/knowledge-model.md`, `references/documentation-templates.md` |
| Architecture and mechanical checks | `references/architecture-diagrams.md`, `references/linter-templates.md` |
| Audit dimensions, weights, and acceptance checks | `references/audit-rubric.json` |
| Parallel work Lanes, coordination Registry, contracts, exact commit ranges, integration approval (I2) | `references/coordination-and-integration.md` |
| Create, attach, detach, or remove a Git worktree | `references/project-skill-architecture.md`, `references/coordination-and-integration.md` |
| Five-Change trigger, periodic Harness review (E1), independent reviewer, accepted update | `references/evolution.md` |
| Existing project Harness update | `references/migration.md` |
| Runtime maintenance or traceback diagnosis | `references/runtime-modules.md` |
| Project identity, links, directory ownership | `references/project-skill-architecture.md` |

## Checkpoints And Failures

- `CHECKPOINT H1`: confirm project identity and update effects before `init` or `migrate`.
- `CHECKPOINT E1`: obtain user approval to start periodic Harness review before acquiring the
  exclusive Evolution lease or staging changes.
- `CHECKPOINT I2`: obtain integration approval only after an Integration candidate, aggregate
  validation, and independent review bound to the exact candidate commit are ready.
- A link collision leaves existing content unchanged and reports the exact path.
- A contract, path, or Git integration-base conflict pauses only affected work and returns to planning.
- Integration applies selected `base_commit..completion_commit` ranges, not a long-lived Lane tip.
- Migration and Evolution candidate, digest, review, validation, or transaction failures rollback
  content and mutable state. Evolution retains its lease and write-lock record when retry evidence
  is required.
- Integration failures before canonical landing leave the target branch unchanged. Failures after
  landing retain the recorded phase and exclusive write lock so retry resumes Registry commit or
  cleanup without landing twice.
- Integration and Evolution share one exclusive write lock.
- Before removing a secondary worktree, verify and detach its shared project Harness links. Stop if
  their target identity or any remaining directory Junction cannot be proven safe.
- Stop the update when a complete bundle still depends on repository prose or machine-specific
  paths, or when an executable artifact lacks explicit authorization and declared validation.

## Maintaining ECL Harness Engineer

For changes to this Skill, read `references/maintainer-capability-contract.md`. For an explicitly
requested external quality evaluation, read `references/darwin-eval-prompts.md`. These references
are not part of project analysis or project Harness operation.
