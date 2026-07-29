# Intake

## Inputs

- User request and accepted user plan, when present.
- Critical rules, L1 overview, Registry preflight, and current Change status.
- Canonical project instructions and evidence relevant to scope.

## Agent Judgment

Classify work as small or structured. Resolve goal, observable acceptance, non-goals, dependencies,
risk, and high-impact unknowns. Do not ask again for decisions already settled by an accepted plan
unless repository evidence conflicts with it.

## Deterministic Commands

- Run `change preflight` before classification.
- Run `change new` only for structured work without an existing applicable Change.
- Run `check_stage_artifacts.py --stage intake` after creating Change evidence.

## Actions

1. Restate the intended outcome and evidence-backed constraints.
2. If preflight reports `refresh-needed`, reload related Registry events/contracts and canonical
   evidence, then replan before using L1/L2/L3 assertions.
3. Identify API, schema, event, config, permission, module, release, or multi-step validation impact.
4. Record assumptions; ask at most three high-impact questions in one round, and only when their
   answers materially change implementation or safety.
5. Create or reuse one Change for structured work and publish its initial scope.

## Outputs

- Small-work decision, or initialized Change id and Lane.
- Observable acceptance, scope, non-goals, assumptions, risks, and unresolved blockers.

## Exit

Acceptance is testable and no unresolved high-impact ambiguity remains. Structured work has one
Change; small work records its verification expectation without entering the evolution count.

## Stop And Escalate

Stop when the target project, requested owner, safety boundary, or acceptance cannot be established
from evidence or one bounded user decision.

## Rules

Apply HR-01, HR-02, HR-22, and HR-23 plus `references/rules/by-stage/intake.md`.
