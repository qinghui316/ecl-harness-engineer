---
name: {{SKILL_NAME}}
description: "Operate the local Harness for {{PROJECT_NAME}}. Use for project work that needs ECL Change planning, layered project knowledge, local worktree coordination, contract checks, Integration, or Harness Evolution."
---

# {{PROJECT_NAME}} Harness

Use this project Harness when the current project id is `{{PROJECT_ID}}`. Its collaboration mode is
`{{MODE}}`.

A Change is one recorded and validated unit of work. The coordination Registry stores shared
worktree facts, and a Lane is one parallel work lane. E1 is the user approval checkpoint that
starts a periodic Harness review. I2 is the user approval to land an independently reviewed
Integration candidate. Both identifiers remain in commands and persisted state.

## Start

1. Read `references/rules/critical.md` and `references/project_wiki/overview.md`.
2. Use the generated `references/project_wiki/catalog.md` to select relevant L2/L3 current,
   target, decision, or guide documents by module and knowledge owner. Follow linked reference-source maps
   only when the task crosses those boundaries.
3. For explanation, navigation, or read-only source research, continue from project knowledge and
   cited implementation evidence without running coordination Registry commands.
4. Classify repository mutations before running commands. In single-Lane mode, Small Changes
   proceed with targeted project verification. In multi-Lane mode, every repository mutation uses
   a Structured Change so its affected paths are recorded before `{{CHANGE_COMMAND}} preflight
   --project-root <cwd>` runs.
5. Read the current workflow and `references/rules/by-stage/<stage>.md` before making that stage's
   decisions.

If the detected project id differs, stop and locate the correct project Harness.

## Classify Work

- **Small:** single-Lane, local, low-risk work without contract, architecture, cross-module, release,
  permission, data, or multi-step validation impact. A formal Change and preflight are optional.
- **Structured:** create one Change, record its scope and high-impact contracts, approve its plan,
  implement, verify, and close with complete evidence.

## Commands

```text
{{PROJECT_COMMAND}} audit|doctor --project-root <path>
{{CHANGE_COMMAND}} new|preflight|publish|status|park|resume|close|search|context|reindex --project-root <path>
{{INTEGRATE_COMMAND}} start|status|complete|abort --project-root <path>
{{EVOLVE_COMMAND}} check|status|stage|mark-complete --project-root <path>
{{KNOWLEDGE_COMMAND}} scan|check --project-root <path>
```

For ordinary current, target, decision, guide, workflow, or rule documentation, read the knowledge
model, update the Markdown directly in the current Structured Change, and let `change reindex` or
`change close` refresh the generated catalog and knowledge source baseline. Use
`kind: current` only for integrated product behavior or current Harness-process facts. Keep an
unintegrated product claim in Change evidence or a target/in-progress document; after landing, a
Structured Change may promote it to current. Use
`references/analysis-contract.md` only for a semantic audit or broad E1 analysis. Migration upgrades
Runtime/schema/templates and does not regenerate project knowledge. E1 follows
`references/workflows/evolve.md`; Agent review expands scope when catalog neighbors reveal an
overlap, while Runtime only validates metadata, links, content digests, and exact conflicts. Use
`references/bootstrap/project.md` only for an approved empty-project bootstrap Change. Read
`references/runtime-modules.md` only to maintain a helper or diagnose a traceback. Read the
Integration workflow before creating, detaching, or removing a worktree.

Read `references/git-collaboration.md` only when creating, sharing, cloning, updating, reviewing, or
diagnosing an independent Git repository for this project Skill. Ordinary project work does not load
or run that Git workflow.

Rerun preflight after material path, contract, or Git integration-base changes, before closing multi-Lane
Structured work, and before Integration. Run knowledge scan/check only for suspected source changes, a
related source-change signal, audit, migration, or E1; these commands report evidence and never
rewrite project knowledge.

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

## Source Precedence

When sources disagree, use the source that owns the question:

```text
coordination state -> Registry integration-base events and contracts
accepted work scope -> current Change spec, plan, and evidence
implemented behavior -> repository code, manifests, configuration, tests, and accepted interfaces
periodic project context -> L1/L2/L3 project knowledge
```

A related source change returns `refresh-needed`; revise the Change before continuing.
`state/changes/` stores complete Change evidence and history. Coordination Registry records align
parallel work Lanes but do not replace implemented behavior or the accepted spec and plan.

## Integration Approval And Harness Evolution Review

Integration applies selected exact completion ranges. The user gives integration approval (I2)
only after aggregate validation and independent review of the exact candidate commit.

Every fifth eligible Change creates a fixed set of Change IDs for periodic Harness review (E1).
Start from those Changes and related owners; widen review only when evidence shows broader drift,
duplication, rule conflict, or structural change. Search related knowledge owners before creating a
document and explain why Merge or Replace is not appropriate. Both focused and complete-analysis
E1 bundles apply only artifacts explicitly named by `creation-delta.json`; Evolution never reruns
the initialization renderer. Apply a staged
Evolution candidate only when an independent review tied to its content digest and the required
validation satisfy `references/audit-rubric.json`; there is no E2.

After canonical landing, the same task directly synchronizes affected current Markdown and runs
`change reindex`. Unlanded product behavior stays in Change evidence or `target/in_progress`.
Routine synchronization does not run migration, Evolution, renderer, independent review, or full
project tests.

## Rule Source

`references/rules/red_lines.yaml` is the machine rule source. `critical.md` and `by-stage/` are
generated views. Workflows list applicable rule IDs without duplicating rule text.
