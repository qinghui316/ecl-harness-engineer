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

A clearly local copy/comment/formatting or single-file fix may remain Small when it has no boundary,
runtime, compatibility, or multi-step validation impact. Small work records assumptions and
verification in the final response and does not count toward Evolution.

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
active -> closing -> completed -> archive
active -> blocked -> archive
active -> abandoned -> archive
```

- Every Change has a globally unique canonical ID before artifacts are created.
- Every worktree has one Lane; a Lane has at most one active or closing Change.
- Different Lanes may work concurrently.
- New claims use exclusive create so simultaneous identical IDs have one winner.
- A terminal Change cannot be reopened by publish.
- Parking preserves complete evidence and frees the Lane for another Change.
- Resume restores the same owner Lane and fails when that Lane already has active work.

## Registry Preflight And Contracts

Pure explanation, navigation, and read-only source research do not require preflight. For repository
mutation, run it once after scope is understood and before planning or editing. Rerun after material
path, contract, or baseline changes and before publish, close, or Integration; do not rerun before
every source read or unchanged stage boundary. Publish project-relative paths. Require a contract
for API, schema, event, configuration, permission, or module-boundary changes.

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

## Git Close

Git close is two-stage because code identity must be exact while Change evidence remains outside
business Git.

1. Complete summary/spec/plan/tasks/review and validation evidence.
2. Run `change prepare-close`; it validates shared evidence and sets `closing`.
3. Commit the business implementation and obtain a clean exact HEAD.
4. Run `change close --completion-commit <head> --validation-passed`.
5. CLI verifies ancestry and clean HEAD, binds completion commit to the Registry record, moves Skill
   evidence to archive, rebuilds INDEX, and runs Evolution threshold check.

For non-Git projects, terminal close is one-stage. Blocked and abandoned Changes archive complete
available evidence but never become evolution-eligible.

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
3. Rescan current canonical project evidence into profile/audit/delta.
4. Classify candidates as Promote, Retain, Merge, Retire, or Archive-only.
5. Prefer improving an existing owner over adding a file/rule/workflow.
6. Stage a complete candidate and validate rules, Wiki, stage artifacts, doctor, checks, and required
   project gates.
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
harness-change prepare-close|close
harness-change search|context|reindex
harness-evolve check|status|stage|mark-complete
```

The launchers select the actual project Harness and host runtime. Do not copy lifecycle
logic into repository scripts or documentation.
