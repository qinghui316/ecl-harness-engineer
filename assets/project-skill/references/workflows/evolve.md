# Evolve

## Inputs

- Frozen five-Change window, compact Registry summaries, selected Change/review evidence, and
  Integration signals.
- Current code/manifests/configuration/tests/interfaces, current project profile, L1/L2/L3, workflows, rules, templates,
  checks, drift findings, and document-entropy findings.
- `references/analysis-contract.md`, which defines the self-contained four-file rescan bundle,
  audit weights, evidence rules, and creation-delta boundary.

## Agent Judgment

Rescan current project facts and classify accumulated experience as Promote, Retain,
Merge, Retire, or Archive-only. Distinguish project knowledge from Harness process rules. Do not
promote unintegrated implementation facts or generic article advice without project evidence.

## Deterministic Commands

- Ask E1, then run `evolve check --e1-confirmed --claim-owner <id>`.
- Run `python scripts/build_analysis_bundle.py --project-root <canonical-root> --output <bundle>`
  to extract a partial draft, then have the Agent review every semantic claim and write the complete
  four-file bundle using `references/analysis-contract.md`.
- Run `evolve stage --proposal-id <id> --owner <id> --analysis-bundle <bundle>` only after the
  evidence-backed proposal and complete rescan bundle exist.
- Run rule generation, Wiki stale, stage artifact, doctor, and applicable project checks against the
  staged candidate.
- Request a native independent judge and any required full test.
- Persist the result using `assets/templates/evolution-judge.json`, bound to the candidate
  fingerprint and a reviewer distinct from the owner.
- Run `evolve mark-complete --judge-report <path>` exactly once for keep/rejected. If no judge is
  available, use `--status noop --judge-unavailable`.

## Actions

1. Freeze the five ids; queue later Changes for the next window.
2. Build and preflight the fresh four-file bundle from implementation evidence using
   `references/analysis-contract.md`.
3. Propose L1/L2/L3, command/environment, workflow, rule, template, check, and entropy changes.
4. Remove duplicate current facts, retire stale guidance, and retain detailed history in archive.
5. Stage and validate the complete project Harness candidate, preserve
   `references/audit-rubric.json`, then recompute its fingerprint before a recoverable whole-root
   publication that preserves current dynamic state.
6. Apply automatically only after score >= 80, no hard issue, and all required validation passes.

## Outputs

- Proposal, evidence classification, updated analysis bundle, judge result, validation report,
  terminal results.tsv row, and either one accepted project Harness update or no modification.

## Exit

Evaluated ids are durable, pending is closed, writer ownership is released, and the terminal result
is keep/rejected/noop. A kept run may update L1/L2/L3 and Harness behavior without E2.

On publication failure, current content and persisted evolution state are restored while the
owner/writer and staged candidate remain available for diagnosis and retry.

## Stop And Escalate

Stop on missing E1, writer collision, unsupported project fact, score below 80, hard issue, failed
validation, or unavailable independent review. Record rejected/noop rather than partially applying.

## Rules

Apply HR-01, HR-04, HR-06 through HR-13, and HR-16 through HR-21 plus
`references/rules/by-stage/evolve.md`.
