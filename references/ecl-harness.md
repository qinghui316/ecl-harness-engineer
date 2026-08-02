# ECL Workflow Reference

## Purpose

Use the Evolution Constraint Language workflow inside one shared project Harness. It provides
explicit requirements, planning, task evidence, validation, handoff, history, and Evolution.

## Owners

| Artifact | Owner and role |
| --- | --- |
| Project Harness `SKILL.md` | Short entry and stage router |
| `references/workflows/` | Stage instructions and exit criteria |
| `references/rules/red_lines.yaml` | Only machine rule source |
| `state/changes/active/` | Current structured Change evidence, one per active Lane |
| `state/changes/parking/` | Paused Changes that may resume |
| `state/changes/archive/` | Complete terminal Change history |
| `state/changes/INDEX.json` | Generated searchable Change index; never hand-edit |
| `state/registry/` | Lane, path, contract, baseline, completion, and Integration facts |
| `state/evolution/` | Five-Change pending, proposals, evaluated IDs, and results |
| Business Git | Accepted code and authoritative business/project documents |

All local worktrees and Codex/Claude runtimes resolve the same physical Skill. Do not create a
separate Change archive, rule manual, status ledger, or evolution state per worktree.

## Small Versus Structured Work

Create a structured Change when work affects multiple modules/files, API/schema/event/config/data,
permissions, architecture, release/runtime behavior, user-visible compatibility, plan review, or a
multi-step validation chain; also create one when uncertainty prevents proving the work is local.

A clearly local copy/comment/formatting or single-file fix may remain Small in single-Lane mode when
it has no boundary, runtime, compatibility, or multi-step validation impact. Small work records
assumptions and verification in the final response and does not count toward Evolution.

In multi-Lane mode, every repository mutation is Structured. Without an atomic path claim, one Lane
cannot prove that another Lane is not concurrently changing the same path.

Decision order:

1. Reuse the current applicable Change on the Lane.
2. Treat obviously local low-risk work as Small.
3. Treat boundary, data, permission, architecture, runtime, release, or multi-module work as
   Structured.
4. Inspect read-only when impact is unclear; ask one material question or upgrade to Structured.

## Intake Review

Support requirement-first, plan-first, and mixed input.

- Requirement-first: ask the smallest set of high-impact questions needed to produce testable
  acceptance, non-goals, constraints, and safety boundaries.
- Plan-first: treat the supplied plan as a draft, split WHAT/WHY into spec and HOW into plan, and
  ask only about gaps that change implementation, compatibility, data, security, or acceptance.
- A complete accepted plan that matches repository evidence does not trigger a repeated interview.
- Ask at most three high-impact questions per round.
- Low-risk unknowns become explicit assumptions.
- High-impact unknowns use `[NEEDS CLARIFICATION: ...]` and block implementation.

## Change Evidence

Each structured Change owns:

```text
summary.md
spec.md
plan.md
tasks.md
reviews/review.md
```

### Summary

Keep phase, outcome, in/out scope, decisions, validation status/evidence, failure attribution,
risks/blockers, next step, and handoff. Summary is the default task context and should not repeat
the complete spec or plan.

### Spec

Keep intake shape, real problem/current behavior/evidence, user or system scenarios, observable
acceptance criteria, non-goals, constraints, assumptions, unresolved questions, and resolved
clarifications. Spec owns WHAT and WHY.

### Plan

Keep technical approach, impacted modules/owners/paths, interfaces/data/permissions/contracts,
planning-discovered spec gaps, risks/mitigations, AC-mapped verification, and plan-review evidence.
Plan owns HOW. A planning-discovered requirement gap returns to spec instead of hiding inside tasks.

### Tasks

Use stable IDs. Each implementation/validation task names AC, owner/path, action, and verification.
Mark parallel-safe work only when ownership and dependency evidence support it. Pending or deferred
tasks must remain visible at close.

### Review

Record intake/spec/plan/code/validation/contract/Integration/knowledge/entropy review. Structured
implementation cannot begin until acceptance is observable, high-impact contracts are published,
and plan review is approved.

## Shared Multi-Lane Lifecycle

```text
new -> active
active -> parking
parking -> active
active -> completed -> archive
active -> blocked -> archive
active -> abandoned -> archive
```

- Every Change has a globally unique canonical ID before artifacts are created.
- Every worktree has one Lane; a Lane has at most one active Change.
- Different Lanes may work concurrently.
- New claims use exclusive create so simultaneous identical IDs have one winner.
- A terminal Change cannot be reopened by publish.
- When work corrects or continues a terminal Change, create a new Change and read the relevant
  archived summary first. In the new spec or summary, name that archive, distinguish inherited
  decisions from superseded assumptions, state the remaining scope, and revalidate those facts
  against current evidence. Keep the archived Change unchanged.
- Parking preserves complete evidence and frees the Lane for another Change.
- Resume restores the same owner Lane and fails when that Lane already has active work.

## Registry Preflight And Contracts

Pure explanation, navigation, read-only source research, and single-Lane Small Changes do not require preflight.
For Structured Changes, create or reuse one Change, publish its initial scope, then run preflight
before plan approval or editing. Rerun after material path, contract, or baseline changes, before a
multi-Lane close, and before Integration; do not rerun before every source read or unchanged stage
boundary. Multi-Lane mutations and any work with Structured impact publish scope before editing.
Publish project-relative paths. Require a contract for API, schema, event, configuration,
permission, or module-boundary changes.

Contracts record kind, stable subject, owner module, operation, affected paths, consumers,
dependencies, compatibility, migration note, evidence, and status. Preflight identifies overlap,
dependency, baseline advancement, and related Wiki drift. It returns replan only for affected scope;
unrelated Lane work continues.

External IDs and paths are untrusted. Reject separators, traversal, absolute paths, non-canonical
filenames, and mismatched record IDs.

## Stage Update Protocol

When Change evidence or shared facts change at a stage boundary:

1. Update summary phase/outcome/next step.
2. Update spec when WHAT/WHY or acceptance changed.
3. Update plan when HOW, ownership, contracts, risk, or verification changed.
4. Update tasks immediately when work completes, blocks, or is deferred.
5. Record review and validation evidence before claiming the stage exit.
6. Publish changed Registry facts and rerun preflight when paths, contracts, or baseline assumptions
   materially changed.

Hook/check tooling may validate but never auto-write Change docs, move state, or rebuild current
facts without the explicit lifecycle command.

## Change Close And Git Boundaries

Close is one-stage in Git and non-Git projects. Complete summary/spec/plan/tasks/review and passing
validation evidence, then run `change close`. The CLI moves Skill evidence to archive, rebuilds
INDEX, and runs the Evolution threshold check without requiring a commit or clean worktree.

`--completion-commit` may record an existing linear commit boundary, but it is optional. When the
user later selects a Change for Integration, `integrate start` requires an exact boundary from that
metadata or `--completion-commit <change-id>=<sha>`. A Change without an isolatable range remains
valid history and Evolution evidence. Blocked and abandoned Changes archive available evidence but
never become evolution-eligible.

## INDEX And Historical Context

`state/changes/INDEX.json` is generated from Registry records and Change summaries after new,
publish, park, resume, close, or explicit reindex. It records Change/Lane/status, scope, paths,
tags, validation, base/completion commit, summary path/excerpt, and update time.

Normal context:

1. Project Harness entry, critical rules, and L1.
2. Registry preflight and current Lane/Change.
3. Current workflow and selected L2/L3.
4. Current Change summary, then details needed for the stage.

Historical context:

1. Search INDEX by ID, scope, path, tag, validation, or summary.
2. Read selected summary.
3. Read spec/plan/tasks/review only for explicit resume, review, failure analysis, Integration, or
   Evolution.

Never preload the entire archive. Complete history remains available; context governance does not
delete evidence.

## Verification And Failure Feedback

Each acceptance criterion needs a command, scenario, runtime observation, or bounded review.
Record command, working directory, exit status, report path, and relevant output. Classify failures:

- introduced: caused by the Change and must be fixed or block close;
- pre-existing: proven against baseline and reported without weakening the gate;
- environmental: missing service/tool/secret or host condition;
- blocked: requires a decision or dependency outside accepted scope.

Repeated failures, user corrections, Integration conflicts, contract drift, and document drift
become Evolution evidence. A one-off bug is not automatically a permanent rule.

## Five-Change Evolution

Eligible Changes are unique, completed, validation-passed, evidence-complete, and non-abandoned.
Integration and Evolution records and Small work are excluded. Any Lane may make the global count
reach five.

At five, create pending but do not block ordinary work. After E1:

1. Atomically claim one evolution owner and freeze five IDs; later Changes queue.
2. Read INDEX and summaries first, then only necessary details and Integration signals.
3. Classify candidates as Promote, Retain, Merge, Retire, or Archive-only.
4. Default to a focused delta for Agent-owned project documents, rules, workflows, templates,
   checks, helpers, or routes; build a complete rescan only when renderer-owned current facts or
   architecture changes.
5. Search catalog by module, Owner, kind, and task terms; read related owners and direct links,
   prefer Merge/Replace, and explain why a new file is necessary.
6. Stage a complete frozen candidate and run affected Harness checks plus necessary project gates.
7. Request an independent judge that did not author the proposal.
8. Apply only for score >= 80, no hard issue, and passing validation/full test.
9. Record keep/rejected/noop, mark evaluated IDs, preserve archive/INDEX/Registry, and clear pending.

There is no E2. Passing work applies after E1. Unavailable judge is dry-run noop. Rejected/noop
must preserve current content; publication is transactional and cannot replace dynamic state with a
stale candidate copy.

## Experience And Entropy

- Promote repeated current project constraints into the best existing rule/workflow/template/check.
- Retain concise current content that still changes correct behavior.
- Merge duplicate current owners and closeout repetition.
- Retire contradicted, superseded, or mechanically enforced prose.
- Keep one-off/historical narrative Archive-only.

Entry is a map, workflows instruct, rules constrain, Wiki maps project facts, Registry coordinates,
Change files explain one task, and archive preserves history. Do not let any owner become a phase
ledger or full changelog.

## Commands

```text
harness-change new|preflight|publish|status
harness-change park|resume
harness-change close
harness-change search|context|reindex
harness-evolve check|status|stage|mark-complete
```

The launchers select the actual project Harness and host runtime. Do not copy lifecycle
logic into repository scripts or documentation.
