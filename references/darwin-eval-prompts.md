# Darwin Evaluation Prompts

Use these prompts only to evaluate ECL Harness Engineer after ordinary validation. A project
Harness has no Darwin dependency. Score behavior and evidence, not expected wording.

## 1. Empty Non-Git Project

```text
Initialize a Harness for an empty non-Git directory with no project brief.
```

Expected: one project-level single-Lane Skill, explicit unknown purpose/commands, no guessed L2/L3,
and an unchanged application/Git setup.

## 2. Mature Project Analysis

```text
Analyze a mature multi-module project with manifests, CI, source, tests, architecture docs, and an
environment example, then describe the project Harness result.
```

Expected: evidenced profile, L1 purpose/flows, boundary-based L2, only proven L3, command statuses,
environment/readiness facts, canonical citations, and accepted checks. Top-level directories alone
must not become modules.

## 3. Repository Integration Footprint

```text
Initialize and then migrate a project Harness. Which business-repository files may be created?
```

Expected: bounded AGENTS/Claude routes, one tracked host-native connector, and common exclude only.
Init and migrate use one project Harness renderer and leave project build/CI ownership unchanged.

## 4. Mature Change Parity

```text
A Structured task starts from a partial plan, exposes a spec gap during planning, later fails one
environmental validation, parks, resumes, and completes. What evidence and gates apply?
```

Expected: intake classification, at most three high-impact questions, WHAT/WHY spec, HOW plan,
spec-gap feedback, plan review, AC-task-validation traceability, environmental failure attribution,
park/resume, review, summary, optional close-time commit metadata, Integration-time exact ranges,
and generated INDEX. Evidence stays in project Harness `state/changes`, not the project repository.

## 5. Selective History

```text
The project Harness has hundreds of archived Changes. What enters default context when resuming one?
```

Expected: INDEX plus selected summaries first; full spec/plan/tasks/review only for relevant
recovery, review, Integration, or Evolution. Never preload all archive bodies.

## 6. Two Worktrees

```text
Two long-lived worktrees each start a Change and touch different modules. How do they coordinate?
```

Expected: one physical project Harness, distinct Lanes and active Change directories, shared INDEX
and per-record Registry, stage preflight, and no direct Worker edits to stable Wiki/rules.

## 7. Contract Conflict

```text
Lane A changes an event schema. Lane B depends on that subject from an older baseline.
```

Expected: machine-readable contract and affected paths; B receives refresh-needed/replan while
unrelated Lanes continue. Current facts outrank periodic L1/L2/L3.

## 8. New Worktree Discovery

```text
A new worktree has no Skill links yet. How can its first Agent attach?
```

Expected: managed route invokes the tracked host-native connector; Git common identity locates the
primary physical Skill; Codex and Claude project-level links resolve to the same target.

## 9. Exact Integration And I2

```text
A long-lived Lane contains two Changes but only the second is selected for Integration.
```

Expected: apply the selected Change's exact recorded range, not Lane tip; allow Integrator conflict
and compatibility work; aggregate tests and independent review bind to one candidate SHA before I2;
canonical landing accepts only that reviewed commit after I2. Integration updates
baseline/Registry/signals, never Wiki, and is not a Change.

## 10. Integration Recovery

```text
Canonical landing succeeds, then a Registry write fails.
```

Expected: recoverable landing phase and retained exclusive-write-lock record; retry completes remaining
Registry/cleanup work idempotently. Do not abort or repeat the canonical merge.

## 11. Fifth-Change Evolution

```text
Five unique validated evidence-complete Changes finish across several Lanes.
```

Expected: one pending set of five Change IDs, E1, one exclusive Evolution lease, current evidence
reanalysis, proposal with
Promote/Retain/Merge/Retire/Archive-only, independent score >= 80, no blocking issue, validation, then
automatic apply. There is no E2. Changes 1-4 start no maintenance Agent.

## 12. Evolution Failure

```text
The independent reviewer is unavailable, or the staged candidate changes after scoring.
```

Expected: unavailable independent review rejects an existing candidate and records noop only when
no candidate exists; tamper is rejected before the transaction; current Skill and mutable state
remain unchanged.

## 13. Evolution Concurrency

```text
Changes 6 and 7 close while the first Evolution candidate is staged and applied.
```

Expected: review of the fixed first set completes, newer Changes queue, and the transaction preserves
the current coordination Registry, full Change archive, INDEX, integrations, contracts, Git
integration base, and Evolution state.

## 14. Documentation Duplication And Stale Content

```text
The generated entry, L1, a workflow, and archived summaries repeat the same current-state history.
```

Expected: keep the entry as route, L1 as periodic map, workflow as procedure, Registry/current
summary as live state, and archive as history. Merge/retire duplicates without deleting history.

## 15. Audit Integrity

```text
Audit a project Harness that has many files but guessed modules, unexecuted commands marked
verified, and no negative tests for checks.
```

Expected: low semantic scores despite file presence. `agents/auditor.md` alone owns the weighting;
findings name evidence, responsible module/document, project Harness effect, and validation.

## 16. Evidence Extractor Boundary

```text
Run the bundled project scanner on a mature repository, then initialize its project Harness directly
from that output without an Analyzer, Auditor, or Creator review.
```

Expected: the scanner returns only `partial` or `bootstrap_only` evidence. It may identify files,
manifests, imports, tests, CI, and command candidates, but it does not certify purpose, module
responsibilities, flows, audit scores, or final initialization artifacts. Semantic initialization requires
the Agent-reviewed bundle with four control files and any declared artifact payloads.

## 17. Reference Source Navigation

```text
A target module adapts a scheduler mechanism from a user-provided reference checkout. How does a
future Agent discover and inspect that relationship from a different worktree?
```

Expected: target analysis excludes reference source from target modules and commands. The target
L2/L3 pages link an evidence-backed reference map, which records inspected commit, files, source
structure, adaptation, boundaries, tests, and citations. The map points to the primary-worktree
checkout; a secondary worktree follows the same project Harness links and detects source changes without
a reference command, profile, or runtime loading state.

## 18. Worktree Teardown Safety

```text
Remove a secondary test worktree that currently exposes the shared project Harness to Codex and
Claude Code. The physical project Harness must remain available to the primary worktree.
```

Expected: read the worktree/Integration route, verify both link targets, detach only the two link
nodes, reject unknown Windows directory Junctions, and then use non-force `git worktree remove`.
Wrong targets or cleanup failures preserve the worktree and shared Harness for diagnosis and retry.
An ordinary feature task does not run this teardown flow.

## 19. Independent Project Skill Git Sharing

```text
Publish this project Skill as an independent Git repository for a teammate who will clone the
business project separately. Keep each member's Change history and coordination state local.
```

Expected: load the Git collaboration reference only for this request; operate from the physical
project Skill root; create the inner ignore, README, and PR template before the first add; share
stable knowledge, rules, workflows, Runtime, assets, agents, and only the portable manifest from
state. Verify the business repository excludes and does not track the nested Skill. A new clone runs
the connector, Doctor repair, and knowledge check, then creates ignored local Changes. Migrate/E1
preserve inner Git metadata and repository files, and a mismatched project id or relevant source
drift stops direct use.
