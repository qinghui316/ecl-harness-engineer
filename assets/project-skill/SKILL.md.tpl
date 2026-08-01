---
name: {{SKILL_NAME}}
description: "Operate the local Harness for {{PROJECT_NAME}}. Use for project work that needs ECL Change planning, layered project knowledge, local worktree coordination, contract checks, Integration, or Harness Evolution."
---

# {{PROJECT_NAME}} Harness

Use this project Harness when the current project id is `{{PROJECT_ID}}`. Its collaboration mode is
`{{MODE}}`.

## Start

1. Read `references/rules/critical.md` and `references/project_wiki/overview.md`.
2. Use the generated `references/project_wiki/catalog.md` to select relevant L2/L3 current,
   target, decision, or guide documents by module and Owner. Follow linked reference-source maps
   only when the task crosses those boundaries.
3. For explanation, navigation, or read-only source research, continue from project knowledge and
   cited implementation evidence without running Registry commands.
4. Classify repository mutations before running commands. In single-Lane mode, Small Changes
   proceed with targeted project verification. In multi-Lane mode, every repository mutation uses
   a Structured Change so its paths are claimed before `{{CHANGE_COMMAND}} preflight
   --project-root <cwd>` runs.
5. Read the current workflow and `references/rules/by-stage/<stage>.md` before making that stage's
   decisions.

If the detected project id differs, stop and locate the correct project Harness.

## Classify Work

- **Small:** single-Lane, local, low-risk work without contract, architecture, cross-module, release,
  permission, data, or multi-step validation impact. A formal Change and preflight are optional.
- **Structured:** create one Change, publish scope and high-impact contracts, approve its plan,
  implement, verify, and close with complete evidence.

## Commands

```text
{{PROJECT_COMMAND}} audit|doctor --project-root <path>
{{CHANGE_COMMAND}} new|preflight|publish|status|park|resume|close|search|context|reindex --project-root <path>
{{INTEGRATE_COMMAND}} start|status|complete|abort --project-root <path>
{{EVOLVE_COMMAND}} check|status|stage|mark-complete --project-root <path>
{{KNOWLEDGE_COMMAND}} scan|check --project-root <path>
```

Use `references/analysis-contract.md` for a semantic audit, focused document migration, or E1.
Focused work uses only the affected Agent-owned documents or Harness owners described by
`references/workflows/evolve.md`. Use
`references/bootstrap/project.md` only for an approved empty-project bootstrap Change. Read
`references/runtime-modules.md` only to maintain a helper or diagnose a traceback. Read the
Integration workflow before creating, detaching, or removing a worktree.

Read `references/git-collaboration.md` only when creating, sharing, cloning, updating, reviewing, or
diagnosing an independent Git repository for this project Skill. Ordinary project work does not load
or run that Git workflow.

Rerun preflight after material path, contract, or baseline changes, before closing multi-Lane
Structured work, and before Integration. Run knowledge scan/check only for suspected drift, a
related preflight signal, audit, migration, or E1; these commands report evidence and never rewrite
project knowledge.

## Stage Route

| Stage | Reference |
| --- | --- |
| Intake | `references/workflows/intake.md` |
| Locate | `references/workflows/locate.md` |
| Plan | `references/workflows/plan.md` |
| Implement | `references/workflows/implement.md` |
| Verify | `references/workflows/verify.md` |
| Close | `references/workflows/close.md` |
| Integrate | `references/workflows/integrate.md` |
| Evolve | `references/workflows/evolve.md` |
| Bootstrap an empty business project | `references/workflows/bootstrap-project.md` |

## Current Evidence

When sources disagree, use this order:

```text
Registry baseline events and contracts
-> current Change evidence
-> repository code, manifests, configuration, tests, and accepted interfaces
-> periodic L1/L2/L3 project knowledge
```

Related drift returns `refresh-needed`; revise the Change before continuing. `state/changes/` owns
complete Change evidence and history. Registry records coordinate Lanes but do not replace the
accepted spec or plan.

## Integration And Evolution

Integration applies selected exact completion ranges. The user confirms I2 only after aggregate
validation and candidate-bound independent review.

Every fifth eligible Change creates an Evolution window. After E1, default to a focused update of
Agent-owned project documents, affected rules, workflows, templates, checks, helpers, or routes.
Build a complete semantic rescan only when renderer-owned current facts or architecture changed. A candidate applies only when its bound Judge
report and validation satisfy `references/audit-rubric.json`; there is no E2.

## Rule Source

`references/rules/red_lines.yaml` is the machine rule source. `critical.md` and `by-stage/` are
generated views. Workflows list applicable rule IDs without duplicating rule text.
