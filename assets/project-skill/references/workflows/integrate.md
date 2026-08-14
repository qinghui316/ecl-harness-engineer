# Integrate

## Inputs

- User-selected completed Changes, canonical Git integration base, exact commit boundaries, and contracts.
- Current Integration records, coordination Registry conflicts, aggregate checks, and review requirements.

## Agent Judgment

Order selected commit ranges by explicit Git Integration dependencies, resolve conflicts as a local PR reviewer, and decide
whether the combined candidate is ready for integration approval (I2). Integration records
knowledge/Evolution signals. The Integration transaction does not rewrite L1/L2/L3; after canonical
landing and lock release, the same task synchronizes only affected current Markdown.

## Deterministic Commands

- Run `integrate start`, supplying `--completion-commit <change-id>=<sha>` for each selected Change
  that did not record an optional boundary at close.
- Use `integrate status --resume` after resolving a recorded cherry-pick conflict.
- Run aggregate project verification and independent review against one exact candidate commit.
- Have an independent reviewer write the `assets/templates/integration-review.json` shape, bound
  to the exact candidate commit SHA, validation commands, findings, and reviewer identity.
- Run `integrate complete --confirm-i2 --review-report <path>` only after explicit integration
  approval (I2).
- On a retry, read `landing_phase` and resume from `pre_merge`, `canonical_landed`,
  `registry_committed`, or `cleanup_complete`; never repeat a completed landing phase.

## Actions

1. Verify each selected linear `base_commit..completion_commit` range. Git ancestry proves range
   shape; the Change author and Integrator must also confirm that it contains no unrelated commits.
2. Before creating the Integration Record or worktree, resolve every `change_dependencies` entry.
   Apply exact ranges in topological order for `kind: integration`; require unselected Git
   dependencies to already belong to a completed Integration Record. Validate `kind: evidence`
   prerequisites as completed, validated, and evidence-complete without selecting or cherry-picking
   them. Never infer dependency kind or merge a long-lived parallel work Lane tip.
3. Resolve conflicts, add compatibility edits, and update authoritative documentation tracked in
   the project repository as needed. Do not update project Harness L1/L2/L3 while the Integration
   transaction holds the exclusive write lock.
4. Record dependency declaration snapshots and separately record satisfied evidence dependencies.
   Bind independent review to the candidate commit and dependency content digest, then recompute
   that digest immediately before landing. Record conflicts, human corrections, contract effects, documentation source changes, and
   knowledge signals.
5. Present the exact candidate commit, combined diff, validation, independent review report, and
   risks for integration approval (I2). After approval, `integrate complete` revalidates that same
   report against the unchanged candidate commit.
6. After the coordination Registry update, verify and detach Codex/Claude project Harness links, reject unknown
   directory Junctions, then remove the temporary worktree without `--force`.
7. After landing and lock release, update affected `current/implemented` Markdown from canonical
   evidence and run `change reindex`. If synchronization fails, report `refresh-needed`; do not
   roll back canonical code or start E1/migrate/Judge.

## Outputs

- Integration candidate/record, combined diff, conflicts and Integrator edits, aggregate validation,
  independent review, canonical commit, integration-base event, and Evolution evidence.

## Exit

After I2, canonical contains the exact reviewed candidate, full contract/affected-path
integration-base event and input Change states are durable, `landing_phase=cleanup_complete`, the
exclusive write lock is released, the temporary worktree is removed, and affected current
knowledge is synchronized or explicitly marked `refresh-needed`. Old parallel work Lanes see
related drift at preflight.

## Stop And Escalate

Stop for a selected Change without an exact commit boundary, nonlinear ranges, unresolved conflict, failed aggregate gate,
missing integration approval (I2), an active exclusive write lock, an unverifiable Harness link
target, or an unknown
directory Junction in the worktree being removed.

## Rules

Apply HR-01, HR-04, HR-05, HR-06, HR-11, HR-15, HR-19, HR-22, and HR-25 plus
`references/rules/by-stage/integrate.md`.
