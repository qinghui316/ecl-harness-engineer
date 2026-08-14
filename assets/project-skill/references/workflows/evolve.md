# Periodic Harness Evolution Review

## Inputs

- Fixed set of five Change IDs, INDEX entries, summaries/reviews, Integration signals, and recorded
  knowledge impacts.
- Related knowledge owners, direct links, rules, workflows, checks, and affected canonical source.
- `references/analysis-contract.md` for focused and broad-analysis bundle requirements.

## Agent Judgment

Classify durable experience as Promote, Retain, Merge, Retire, or Archive-only. Do not repeat
ordinary current facts already synchronized after canonical landing. Search the complete rule source
before adding a rule. Search the Catalog by module, knowledge owner, kind, and task terms before
creating knowledge; prefer Merge or Replace and explain why an existing owner cannot carry a new
document.

Start with the five Changes and related owners. Expand to the complete Catalog, complete rule source,
or wider project analysis when evidence reveals cross-owner duplication, broad drift, global rule
conflict, or structural change. Runtime never decides this scope from keywords or file counts.

## Deterministic Commands

- After E1 approval, run `evolve check --e1-confirmed --claim-owner <id>`.
- Create `creation-delta.json` with `mode: evolution-focused` and declared artifacts. When broad
  project analysis is required, provide the complete four control files; only its explicit creation
  delta can modify the candidate.
- Run `evolve stage --proposal-id <id> --owner <id> --analysis-bundle <bundle>`.
- Run affected Harness checks and only the project validation required by changed owners/contracts.
- Request an independent reviewer after stage returns the candidate content digest.
- Use `evolve mark-complete --candidate-id <id> --judge-report <path>` for `keep` or `rejected`.
  If review is unavailable, record a staged candidate as `rejected --judge-unavailable`; use
  `noop --judge-unavailable` only when no candidate exists.

## Actions

1. Keep the fixed five Change IDs; later Changes remain queued.
2. Review related owners and widen scope only with a recorded reason.
3. Merge duplicate rules/current facts, retire contradicted or mechanically superseded guidance,
   and keep task history in Change archive.
4. Stage only Create/Replace/Merge/Retire artifacts named by the delta. Profile, architecture, and
   audit files are evidence and are not installed or rendered.
5. Bind independent review to the exact candidate digest. Apply only `keep` after score >= 80, no
   blocking issue, and required validation.

## Outputs

- A concise proposal, explicit scope expansion when any, creation delta/artifacts, validation,
  independent review, terminal result, and either one accepted update or no content change.

## Exit

`keep` requires and applies a source-fresh candidate. `rejected` requires a candidate, verifies its
integrity and review binding, but never applies it; later source drift does not block recording the
rejection. `noop` requires no candidate. Every terminal path records evaluated IDs, clears pending
and staging, and releases the Evolution lease and write lock.

On transaction failure, restore current content and persisted Evolution state while retaining the
lease, write-lock record, and candidate for diagnosis and retry.

## Stop And Escalate

Stop on missing E1, write-lock collision, unsupported durable fact, candidate tampering, blocking
issue, or failed required validation. Never hide a staged candidate behind `noop`.

## Rules

Apply HR-01, HR-04, HR-06 through HR-13, and HR-16 through HR-21 plus
`references/rules/by-stage/evolve.md`.
