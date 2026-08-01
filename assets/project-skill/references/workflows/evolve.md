# Evolve

## Inputs

- Frozen five-Change window, compact Registry summaries, selected Change/review evidence, and
  Integration signals.
- Current project knowledge, workflows, rules, templates, checks, relevant drift findings, and
  canonical evidence only when the proposal affects project semantics.
- `references/analysis-contract.md`, which defines focused delta and full-refresh bundle boundaries.

## Agent Judgment

Classify accumulated experience as Promote, Retain, Merge, Retire, or Archive-only. Distinguish
project knowledge from Harness process rules. Default to focused Evolution. Require a full refresh
only when purpose, modules, L1/L2/L3, reference maps, architecture, commands, environment, or
related knowledge drift changes. Do not promote unintegrated implementation facts or generic
article advice without project evidence.

## Deterministic Commands

- Ask E1, then run `evolve check --e1-confirmed --claim-owner <id>`.
- For focused work, create `creation-delta.json` with `mode: evolution-focused` and only the named
  artifacts. For full refresh, run the draft extractor and complete the four-file bundle.
- Run `evolve stage --proposal-id <id> --owner <id> --analysis-bundle <bundle>` after the proposal
  and selected bundle exist. Stage validates the bundle; a separate project audit is not required.
- Run the affected Harness checks and necessary project validation. Run a full project test only
  when the changed owner or project contract requires it.
- After stage returns the frozen candidate fingerprint, immediately request a native independent
  Judge. The author cannot act as the Judge.
- Persist the result using `assets/templates/evolution-judge.json`, bound to the candidate
  fingerprint and a reviewer distinct from the owner.
- Run `evolve mark-complete --judge-report <path>` exactly once for keep/rejected. If no judge is
  available, use `--status noop --judge-unavailable`.

## Actions

1. Freeze the five ids; queue later Changes for the next window.
2. Select focused delta by default; select a four-file refresh only for semantic project knowledge.
3. Propose only evidence-backed knowledge, workflow, rule, template, check, and entropy changes.
4. Remove duplicate current facts, retire stale guidance, and retain detailed history in archive.
5. Stage and validate the complete project Harness candidate, preserve
   `references/audit-rubric.json`, then recompute its fingerprint before a recoverable whole-root
   publication that preserves current dynamic state.
6. Apply automatically only after score >= 80, no hard issue, and all required validation passes.

## Outputs

- Proposal, evidence classification, focused delta or full bundle, judge result, validation report,
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
