# Plan

## Inputs

- Change spec, locate evidence, current coordination Registry contracts, and canonical Git
  integration base.
- Project command and verification catalogs.
- Applicable L2/L3 knowledge and current stage rules.

## Agent Judgment

Choose the smallest coherent implementation that meets acceptance. Distinguish compatibility facts
from preferences, and distinguish configured commands from adapter-derived candidates.

## Deterministic Commands

- After recording initial scope with `change publish`, run `change preflight` before finalizing the
  plan and again only after materially changing path, contract, or Git integration-base claims.
- Run `change publish` with paths and a contract when high-impact boundaries change.
- Run `check_stage_artifacts.py --stage plan` before requesting plan approval.

## Actions

1. Map each acceptance criterion to an assigned owner, task, and validation command.
2. Record affected paths and dependencies in the coordination Registry.
3. Record API/schema/event/config/permission/module contracts when required.
4. Define compatibility, migration, rollback-at-code-level, risk, and test strategy.
5. Resolve coordination Registry conflicts and obtain the project-native plan approval.

## Outputs

- Approved `plan.md`, executable `tasks.md`, path claims, optional contract, and validation plan.

## Exit

Every task traces to acceptance; assignment, compatibility, dependencies, and verification are
explicit; no unresolved coordination Registry conflict or high-impact ambiguity remains.

## Stop And Escalate

Stop when another parallel work Lane holds an incompatible path/contract claim, a required command
is only speculative, or approval has not been obtained.

## Rules

Apply HR-01, HR-02, HR-03, HR-17, and HR-18 plus `references/rules/by-stage/plan.md`.
