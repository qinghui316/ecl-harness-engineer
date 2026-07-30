# Plan

## Inputs

- Change spec, locate evidence, current Registry contracts, and canonical baseline.
- Project command and verification catalogs.
- Applicable L2/L3 knowledge and current stage rules.

## Agent Judgment

Choose the smallest coherent implementation that meets acceptance. Distinguish compatibility facts
from preferences, and distinguish configured commands from adapter-derived candidates.

## Deterministic Commands

- Run `change preflight` before finalizing the plan and again after materially changing path or
  contract claims.
- Run `change publish` with paths and a contract when high-impact boundaries change.
- Run `check_stage_artifacts.py --stage plan` before requesting plan approval.

## Actions

1. Map each acceptance criterion to an owner, task, and validation command.
2. Publish affected paths and dependencies.
3. Publish API/schema/event/config/permission/module contracts when required.
4. Define compatibility, migration, rollback-at-code-level, risk, and test strategy.
5. Resolve Registry conflicts and obtain the project-native plan approval.

## Outputs

- Approved `plan.md`, executable `tasks.md`, path claims, optional contract, and validation plan.

## Exit

Every task traces to acceptance; owner, compatibility, dependencies, and verification are explicit;
no unresolved Registry conflict or high-impact ambiguity remains.

## Stop And Escalate

Stop when another Lane owns an incompatible path/contract, a required command is only speculative,
or approval has not been obtained.

## Rules

Apply HR-01, HR-02, HR-03, HR-17, and HR-18 plus `references/rules/by-stage/plan.md`.
