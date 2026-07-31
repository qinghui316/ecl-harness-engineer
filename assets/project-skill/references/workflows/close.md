# Close

## Inputs

- Completed or blocked tasks, review, validation evidence, and current Change state.
- Current Change files and Registry record.

## Agent Judgment

Choose completed, blocked, or abandoned honestly. Completion depends on accepted evidence and
passing validation; Git state and Integration intent do not determine whether the Change qualifies.

## Deterministic Commands

- In multi-Lane mode, rerun `change preflight` for a Structured Change before close. Single-Lane
  work reruns it only after material path, contract, or baseline changes.
- Run `check_stage_artifacts.py --stage close`.
- Run `change close` once to validate evidence and archive the terminal Change.
- Rebuild the Skill-owned Change INDEX after every terminal close.
- Run `evolve check` after terminal close.

## Actions

1. Update summary/review with outcome, validation, risks, and handoff.
2. Resolve or document every pending task.
3. Close the Change without requiring a Git commit; optionally record an existing commit boundary.
4. Publish the compact terminal Registry record and evolution eligibility.
5. Record known follow-up as a next action. Later work uses a new Change whose spec or summary
   references this archived Change; do not mutate terminal evidence.

## Outputs

- Terminal Change record, validation summary, handoff, optional Integration boundary, and pending
  status when the fifth qualified Change is reached.

## Exit

Status is completed, blocked, or abandoned. Only completed, validation-passed, evidence-complete
Changes are eligible for evolution.

## Stop And Escalate

Stop when shared Change evidence is incomplete, an explicitly supplied commit boundary is invalid,
or validation and claimed status disagree.

## Rules

Apply HR-01, HR-06, HR-07, HR-08, and HR-12 plus `references/rules/by-stage/close.md`.
