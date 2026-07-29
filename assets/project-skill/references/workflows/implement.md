# Implement

## Inputs

- Approved plan/tasks and current Change evidence.
- Latest Registry preflight and applicable contract.
- Relevant L2/L3 knowledge, project rules, and existing implementation patterns.

## Agent Judgment

Follow current project patterns and accepted scope. New implementation discoveries may change the
plan or contract, but they do not silently expand scope or rewrite stable shared knowledge.

## Deterministic Commands

- Run `change preflight` at stage entry and after material contract discoveries.
- Run targeted format, compile, lint, or test commands listed in project knowledge.
- Update Change task evidence after verified milestones.

## Actions

1. Read complete relevant implementations before editing.
2. Implement in dependency order and preserve unrelated changes.
3. Republish contract facts when implementation changes an accepted boundary.
4. Record deviations, introduced risks, and exact validation evidence in the Change.

## Outputs

- Scoped source/config/document changes and current task status.
- Updated path/contract facts and implementation evidence.

## Exit

All accepted implementation tasks are complete or explicitly deferred, with no unauthorized scope
expansion and no unresolved contract conflict.

## Stop And Escalate

Stop for stale baseline that invalidates the plan, unexpected permission/data/API impact, unrelated
user-change collision, or a required project gate that cannot be run safely.

## Rules

Apply HR-01, HR-02, HR-03, HR-04, and HR-11 plus `references/rules/by-stage/implement.md`.
