# Close

## Inputs

- Completed or blocked tasks, review, validation evidence, and current commit state.
- Current Change files and Registry record.

## Agent Judgment

Choose completed, blocked, or abandoned honestly. A completed Git Change must have evidence and an
exact clean completion commit; a partial result does not qualify for evolution.

## Deterministic Commands

- Run `check_stage_artifacts.py --stage close`.
- Run `change prepare-close` to validate project Harness evidence and enter `closing`.
- Commit the business implementation, then rerun `change close` with exact clean HEAD.
- Rebuild the Skill-owned Change INDEX after every terminal close.
- Run `evolve check` after terminal close.

## Actions

1. Update summary/review with outcome, validation, risks, and handoff.
2. Resolve or document every pending task.
3. Complete the two-step Git close, or the single-step non-Git close.
4. Publish the compact terminal Registry record and evolution eligibility.

## Outputs

- Terminal Change record, exact completion commit when Git-backed, validation summary, and pending
  status when the fifth qualified Change is reached.

## Exit

Status is completed, blocked, or abandoned. Only completed, validation-passed, evidence-complete
Changes are eligible for evolution.

## Stop And Escalate

Stop when shared Change evidence is incomplete, the implementation worktree is dirty, the exact
completion commit is invalid, or validation and claimed status disagree.

## Rules

Apply HR-01, HR-06, HR-07, HR-08, HR-12, and HR-14 plus `references/rules/by-stage/close.md`.
