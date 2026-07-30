---
name: {{SKILL_NAME}}
description: "Operate the local Harness for {{PROJECT_NAME}}. Use for project work that needs ECL Change planning, layered project knowledge, local worktree coordination, contract checks, Integration, or Harness Evolution."
---

# {{PROJECT_NAME}} Harness

Use this project Harness when the current project id is `{{PROJECT_ID}}`. Its collaboration mode is
`{{MODE}}`.

## Start

1. Read `references/rules/critical.md` and `references/project_wiki/overview.md`.
2. Read the relevant L2 module or system pages, then follow linked L3 bridges and reference-source
   maps when the task crosses those boundaries.
3. For explanation, navigation, or read-only source research, continue from project knowledge and
   cited implementation evidence without running Registry commands.
4. Before planning or editing a repository mutation, run `{{CHANGE_COMMAND}} preflight
   --project-root <cwd>` and read the Lane, Registry, and current Change records it names.
5. Read the current workflow and `references/rules/by-stage/<stage>.md` before making that stage's
   decisions.

If the detected project id differs, stop and locate the correct project Harness.

## Classify Work

- **Small:** local, low-risk work without contract, architecture, cross-module, release, permission,
  data, or multi-step validation impact. A formal Change is optional.
- **Structured:** create one Change, publish scope and high-impact contracts, approve its plan,
  implement, verify, and close with complete evidence.

## Commands

```text
{{PROJECT_COMMAND}} audit|doctor --project-root <path>
{{CHANGE_COMMAND}} new|preflight|publish|status|park|resume|prepare-close|close|search|context|reindex --project-root <path>
{{INTEGRATE_COMMAND}} start|status|complete|abort --project-root <path>
{{EVOLVE_COMMAND}} check|status|stage|mark-complete --project-root <path>
{{KNOWLEDGE_COMMAND}} scan|check --project-root <path>
```

Use `references/analysis-contract.md` for a semantic audit or E1 rescan. Use
`references/bootstrap/project.md` only for an approved empty-project bootstrap Change. Read
`references/runtime-modules.md` only to maintain a helper or diagnose a traceback. Read the
Integration workflow before creating, detaching, or removing a worktree.

Rerun preflight after material path, contract, or baseline changes and before publish, close, or
Integration. Run knowledge scan/check only for suspected drift, a related preflight signal, audit,
migration, or E1; these commands report evidence and never rewrite project knowledge.

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

Every fifth eligible Change creates an Evolution window. After E1, the owner rescans canonical
evidence and accumulated experience. A candidate applies only when its bound Judge report and
validation satisfy `references/audit-rubric.json`; there is no E2.

## Rule Source

`references/rules/red_lines.yaml` is the machine rule source. `critical.md` and `by-stage/` are
generated views. Workflows list applicable rule IDs without duplicating rule text.
