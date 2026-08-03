# Intake

## Inputs

- User request and accepted user plan, when present.
- Critical rules, L1 overview, and current project evidence.
- Canonical project instructions and evidence relevant to scope.

## Agent Judgment

Classify work as small or structured. Resolve goal, observable acceptance, non-goals, dependencies,
risk, and high-impact unknowns. Do not ask again for decisions already settled by an accepted plan
unless repository evidence conflicts with it.

## Deterministic Commands

- Single-Lane Small work does not require `change preflight`; run its targeted project verification
  after editing. Treat every multi-Lane repository mutation as Structured so path claims are
  recorded through an exclusive coordination Registry update.
- Run `change new` only for structured work without an existing applicable Change, record its
  initial scope with `change publish`, then run `change preflight` before plan approval or editing.
- Run `check_stage_artifacts.py --stage intake` after creating Change evidence.

## Actions

1. Restate the intended outcome and evidence-backed constraints.
2. Identify API, schema, event, config, permission, module, release, or multi-step validation impact.
3. For structured work, record initial paths/contracts and run preflight. If it reports
   `refresh-needed`, reload related coordination Registry events/contracts and current implementation evidence
   before relying on periodic L1/L2/L3 assertions.
4. Record assumptions; ask at most three high-impact questions in one round, and only when their
   answers materially change implementation or safety.
5. Create or reuse one Change for structured work and record its initial scope. If the request
   corrects or continues a terminal Change, read its archived summary, create a new Change, and
   explain in the new spec or summary which accepted decisions still apply, which assumptions are
   superseded, and what work remains. Recheck those facts against the current Git integration base,
   contracts, and implementation; do not reopen or edit the archived evidence.
6. Upgrade Small work to Structured before editing when the project is multi-Lane or inspection
   reveals contract, cross-module, data, permission, architecture, release, or multi-step validation impact.

## Outputs

- Small-work decision, or initialized Change ID and parallel work Lane.
- Observable acceptance, scope, non-goals, assumptions, risks, and unresolved blockers.

## Exit

Acceptance is testable and no unresolved high-impact ambiguity remains. Structured work has one
Change; small work records its verification expectation without entering the evolution count.

## Stop And Escalate

Stop when the target project, requested component responsibility, safety boundary, or acceptance
cannot be established from evidence or one bounded user decision.

## Rules

Apply HR-01, HR-02, HR-22, and HR-23 plus `references/rules/by-stage/intake.md`.
