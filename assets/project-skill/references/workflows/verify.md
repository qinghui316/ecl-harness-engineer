# Verify

## Inputs

- Acceptance criteria, changed paths, current contract, and implementation evidence.
- Project command/verification catalogs with configured/candidate/executed status.
- Review requirements and baseline failures.

## Agent Judgment

Select verification proportional to impact. Classify every failure as introduced, pre-existing,
environmental, or blocked; inspection alone is never completion evidence.

## Deterministic Commands

- Run targeted checks first, then aggregate/full gates for shared or high-impact behavior.
- Run project-specific mechanical checks only when they are accepted and listed in the profile.
- Run `check_stage_artifacts.py --stage verify` before close.

## Actions

1. Verify each acceptance criterion with a command, test, runtime observation, or bounded review.
2. Validate contracts, compatibility, documentation, encoding, and generated artifacts as applicable.
3. Compare failures with the captured baseline and record residual risk.

## Outputs

- Command, working directory, exit status, result evidence, and failure attribution.
- Acceptance matrix, review result, and residual risks.

## Exit

All required checks pass, or the Change is explicitly blocked with reproducible evidence and no
false completion claim.

## Stop And Escalate

Stop after the project-defined retry limit, on environmental prerequisites requiring user action,
or when a failure lies outside accepted scope.

## Rules

Apply HR-01, HR-04, and HR-18 plus `references/rules/by-stage/verify.md`.
