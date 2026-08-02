# Five-Change Harness Evolution

## Trigger

Maintain a global set of evaluated Change ids. A Change is eligible when it is unique, completed,
validated, evidence-complete, and not abandoned. Integration Records, Evolution work, and small
tasks without a Change are excluded.

When five unevaluated eligible Changes exist, create `state/evolution/pending.json`. Any Lane may make
the global count reach five. A pending file is a reminder, not a lock on ordinary work.

## Ownership

After E1 approval, acquire `state/registry/locks/evolution-owner/` using an atomic directory create.
If another owner exists, report it and do not start a second evolution. Remove the claim only after
a terminal result or an explicit blocked record. Store the current non-state Harness content
fingerprint in the owner record; this is an integrity check, not a snapshot or rollback system.
The claim freezes that run's Change ids. Changes completed during the run queue for the next window
and must not be silently marked evaluated by the current proposal.

## Evidence Window

Read the Change INDEX and compact Registry summaries first. Read project Harness Change
summaries and reviews only when needed.
Unintegrated Changes may reveal workflow, correction, or validation evidence, but their product
implementation details alone cannot become stable project rules before canonical integration.

## Proposal

Create a proposal before editing current Harness content. Classify every candidate:

- Promote: repeated evidence warrants a current rule, template, script, test, or knowledge entry.
- Retain: the current rule still covers a live risk.
- Merge: duplicate current rules should become one shorter rule.
- Retire: current guidance is stale or mechanically superseded.
- Archive-only: evidence is historical or one-off and should not enter current context.

Prefer improving an existing owner over adding a new file or workflow.
Before creating project knowledge, search the catalog by module, Owner, kind, and task terms; read
the matching owner, directly linked documents, and likely semantic neighbors. A proposal that adds
a document explains why Merge or Replace is not appropriate. Keep Change history in archive rather
than copying it into stable knowledge.

## Independent Gate

Use a native independent agent that did not author the proposal. Score:

| Dimension | Weight |
| --- | ---: |
| Evidence grounding | 30 |
| Project relevance | 25 |
| Mechanical enforceability | 15 |
| Regression safety | 20 |
| Context cost | 10 |

Apply only when score is at least 80, no hard issue exists, and the stated Harness/project
validation passes, including any declared required full test. A dry-run score can never produce
`keep`. If no independent judge is available, record `noop` with `--judge-unavailable` and do not
apply.
The candidate must preserve `references/audit-rubric.json`; Evolution cannot change the formula or
weaken the gate used to judge its own publication.

## Apply

There is no E2. A passing proposal applies automatically after E1. Validate intended files before
publication and use atomic writes. Temporary staging is an implementation detail and must be
deleted; do not create a persistent snapshot, rollback product, or second canonical Skill.

Record one terminal row in `state/evolution/results.tsv` with timestamp, proposal id, evaluated
Change ids, score, status, eval mode, and note. Allowed statuses are `keep`, `rejected`, and `noop`.
Update the evaluated id set and clear pending only after the terminal result is durable.

Before terminal publication, reject `rejected/noop` if current non-state Harness content differs
from the owner fingerprint, and reject `keep` if it does not differ. A kept result increments
`manifest.skill_revision`.

Default to a focused `creation-delta.json` candidate for Agent-owned L1/L2/L3 documents, rules,
workflows, templates, checks, helpers, and routes. Its Experience Retention Scan starts from the
five Changes, affected catalog entries, matching Owners/modules, and direct links; expand only when
evidence reveals a wider overlap. Full Evolution or an explicit semantic audit reviews the whole
catalog. Require the complete four-file analysis bundle only when renderer-owned current facts,
architecture, reference maps, commands, environment, or related knowledge drift changes. Stage
validates the selected bundle directly; standalone project audit remains diagnostic.

Stage a complete non-state Skill candidate. Recompute its fingerprint immediately before mutation
and reject any post-validation candidate or bound-source change. Publication prepares a complete
replacement root, moves the current dynamic `state` into it, and switches the Skill root as one
recoverable filesystem transaction; it never copies stale Registry state from the candidate.
Temporary journal, previous-root, and state-file backups exist only until commit/rollback and are
not a snapshot product. The content-publication lock serializes short Registry mutations during the
root switch, while the shared writer prevents Integration finalization from overlapping Evolution.

Hold the Evolution state lock while validating the frozen owner window, publishing, appending the
terminal result, updating evaluated ids, and computing the next window. On failure, restore both
content and persisted state snapshots while retaining owner/writer evidence for diagnosis and
retry. Changes completed during proposal/staging remain allowed and queue normally.

Do not run a Maintenance Agent for Changes one through four. Integration records canonical and
Registry outcomes as evidence; it does not refresh project Wiki content or trigger evolution by
itself.
