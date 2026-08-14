# Periodic Harness Evolution Review

## Trigger

Maintain a global set of evaluated Change ids. A Change is eligible when it is unique, completed,
validated, evidence-complete, and not abandoned. Integration Records, Evolution work, and small
tasks without a Change are excluded.

When five unevaluated eligible Changes exist, create `state/evolution/pending.json`. Any parallel
work Lane may make the global count reach five. A pending file is a reminder, not a lock on ordinary
work. E1 is the user approval checkpoint that authorizes this review; commands and persisted state
retain the `E1` identifier for compatibility.

Order eligible Changes by `updated_at`, then `change_id`, and place the first five IDs in
`pending.json`. E1 approval binds that recorded set. The lease copies the same IDs and rejects a
mismatch; later eligible Changes remain queued for the next review.

## Exclusive Evolution Lease

After E1 approval, acquire the exclusive Evolution lease at
`state/registry/locks/evolution-owner/` using an atomic directory create. If another process holds
the lease, report it and do not start a second review. Release the lease only after a terminal
result. On failure, retain it for diagnosis and retry rather than inventing a separate blocked
Evolution state. Store the current non-state Harness content digest in the lease record; this
verifies later changes but does not provide a snapshot or rollback. The lease records the fixed set
of Change IDs under review. Changes completed during the review queue for the next set and must not
be marked evaluated by the current proposal.

The E1 claim command first acquires the exclusive write lock, then creates the Evolution lease. It
holds both through proposal authoring, candidate staging, independent review, and terminal result;
this intentionally prevents Integration finalization during the full review. Terminal cleanup
releases the lease before the write lock. The command-level filesystem lock remains outermost, and
the short `evolution-state` Registry lock is acquired only inside it.

## Evidence Set

Read the Change INDEX and compact Registry summaries first. Read project Harness Change
summaries and reviews only when needed.
Unintegrated Changes may reveal workflow, correction, or validation evidence, but their product
implementation details alone cannot become stable project rules before Integration into the
recorded target branch.

## Proposal

Create a proposal before editing current Harness content. Classify every candidate:

- Promote: repeated evidence warrants a current rule, template, script, test, or knowledge entry.
- Retain: the current rule still covers a live risk.
- Merge: duplicate current rules should become one shorter rule.
- Retire: current guidance is stale or mechanically superseded.
- Archive-only: evidence is historical or one-off and should not enter current context.

`Retain` is a proposal classification for existing content. Terminal status `keep` means the staged
candidate was accepted and applied; the two terms are not interchangeable.

Prefer improving an existing owner over adding a new file or workflow.
Before creating project knowledge, search the catalog by module, knowledge owner, kind, and task
terms; read documents with the same knowledge owner, directly linked documents, and likely semantic
neighbors. A proposal that adds
a document explains why Merge or Replace is not appropriate. Keep Change history in archive rather
than copying it into stable knowledge.

## Independent Review

Use a native independent agent that did not author the proposal. Score:

| Dimension | Weight |
| --- | ---: |
| Evidence grounding | 30 |
| Project relevance | 25 |
| Mechanical enforceability | 15 |
| Regression safety | 20 |
| Context cost | 10 |

Apply only when score is at least 80, no blocking issue exists, and the stated Harness/project
validation passes, including any declared required full test. A dry-run score can never produce
`keep`. Status `keep` means accepted and applied. Status `noop` means review completed with no
candidate because no lasting update was needed. If no independent reviewer is available, record a
staged candidate as `rejected --judge-unavailable`; use `noop --judge-unavailable` only when no
candidate was formed.
The candidate must preserve `references/audit-rubric.json`; Evolution cannot change the formula or
weaken the acceptance checks used for its own review.

## Apply The Accepted Update

There is no E2. A passing proposal applies automatically after E1. Validate intended files before
applying the update and use atomic writes for individual files. Temporary staging is an
implementation detail and must be
deleted; do not create a persistent snapshot, rollback product, or second project Harness root.

Record one terminal row in `state/evolution/results.tsv` with timestamp, proposal id, evaluated
Change ids, score, status, eval mode, and note. Allowed statuses are `keep`, `rejected`, and `noop`.
Update the evaluated id set and clear pending only after the terminal result is durable.

Before recording any terminal result, require current non-state Harness content to match the
pre-review digest in the Evolution lease. `keep` and `rejected` require a staged candidate and an
independent report bound to its exact candidate digest; only `keep` applies it. `noop` requires no
candidate and a null candidate digest. A kept result increments `manifest.skill_revision`.

Default to `creation-delta.json + artifacts/` for agent-maintained L1/L2/L3 documents, rules,
workflows, templates, checks, helpers, and routes. Start from the five Change summaries/reviews,
Integration signals, knowledge impacts, affected catalog entries, matching knowledge owners and
direct links. Review retained, merged, removed, and archived knowledge. Expand to the complete
Catalog, complete rule source, or wider source analysis only when evidence reveals cross-owner
duplication, broad drift, a global rule conflict, or structural change.

When broad source analysis is useful, E1 may accept the complete four-file analysis bundle as
evidence. It still applies only the Create/Replace/Merge/Retire entries explicitly named in
`creation-delta.json`; profile, architecture, and audit are not installed into `state/analysis` and
do not invoke the project Wiki renderer. An explicit semantic audit remains read-only.

Stage a complete non-state Skill candidate. Recompute its content digest immediately before the
transaction and reject any candidate modification after validation. For `keep`, also reject a
source-state change made after staging. A rejected candidate may still be recorded after source
drift because it is never applied. Prepare a
complete replacement root, move the current mutable `state` into it, and replace the Skill root
through a crash-recoverable filesystem transaction with rollback; never copy stale coordination
Registry state from the candidate. The transaction journal, previous root, and state-file backups
exist only until commit or rollback and are not persistent snapshots. The filesystem operation lock
serializes short coordination Registry mutations during root replacement, while the exclusive
write lock prevents Integration finalization from overlapping Evolution.

Hold the Evolution state lock while validating the fixed set of Change IDs, applying the candidate,
appending the terminal result, updating evaluated IDs, and computing the next set. On failure,
restore both content and persisted state snapshots while retaining the Evolution lease and
exclusive-write-lock records for diagnosis and retry. Changes completed during proposal or staging
remain allowed and queue normally.

Do not run an Evolution reviewer for Changes one through four. Integration records canonical and
Registry outcomes as evidence; after landing, the same task directly synchronizes affected current
Markdown and runs `change reindex`. That lightweight synchronization does not trigger Evolution.
