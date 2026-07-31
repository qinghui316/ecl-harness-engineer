# Integrate

## Inputs

- User-selected completed Changes, canonical baseline, exact commit boundaries, and contracts.
- Current Integration records, Registry conflicts, aggregate checks, and review requirements.

## Agent Judgment

Order selected commit ranges by dependency, resolve conflicts as a local PR reviewer, and decide
whether the combined candidate is ready for I2. Integration records knowledge/evolution signals but
does not rewrite stable L1/L2/L3 or global rules.

## Deterministic Commands

- Run `integrate start`, supplying `--completion-commit <change-id>=<sha>` for each selected Change
  that did not record an optional boundary at close.
- Use `integrate status --resume` after resolving a recorded cherry-pick conflict.
- Run aggregate project verification and independent review against one exact candidate commit.
- Have an independent reviewer write the `assets/templates/integration-review.json` shape, bound
  to the exact candidate SHA, validation commands, findings, and reviewer identity.
- Run `integrate complete --confirm-i2 --review-report <path>` only after explicit I2.
- On a retry, read `landing_phase` and resume from `pre_merge`, `canonical_landed`,
  `registry_committed`, or `cleanup_complete`; never repeat a completed landing phase.

## Actions

1. Verify each selected linear `base_commit..completion_commit` range.
2. Apply ranges in dependency order; never merge a long-lived Lane tip.
3. Resolve conflicts, add compatibility edits, and update canonical business documents as needed.
4. Record conflicts, human corrections, contract effects, documentation drift, and knowledge signals.
5. Present combined diff, validation, review, and risks for I2.
6. After Registry commit, verify and detach Codex/Claude project Harness links, reject unknown
   directory Junctions, then remove the temporary worktree without `--force`.

## Outputs

- Integration candidate/record, combined diff, conflicts and Integrator edits, aggregate validation,
  independent review, canonical commit, baseline event, and evolution evidence.

## Exit

After I2, canonical contains the exact reviewed candidate, full contract/affected-path baseline event and
input Change states are durable, `landing_phase=cleanup_complete`, the writer is released, and the
temporary worktree is removed. Shared project knowledge waits for Evolution; affected old Lanes see
`refresh-needed` at preflight.

## Stop And Escalate

Stop for a selected Change without an exact commit boundary, nonlinear ranges, unresolved conflict, failed aggregate gate,
missing I2, an active shared writer owner, an unverifiable Harness link target, or an unknown
directory Junction in the worktree being removed.

## Rules

Apply HR-01, HR-04, HR-05, HR-06, HR-11, HR-15, HR-19, HR-22, and HR-25 plus
`references/rules/by-stage/integrate.md`.
