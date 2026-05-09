# Darwin Evaluation Prompts

Use these dry-run prompts when evaluating ecl-harness-engineer quality with darwin-skill.
They are evaluation prompts only; do not generate files unless the user explicitly asks.

## Prompt 1: Existing TypeScript Project

```text
Use ecl-harness-engineer to create an ECL-aware Harness for an existing TypeScript project.
The project already has package.json, src/, and tests/, but no AGENTS.md or harness/.
Explain the files you would create and the validation commands.
```

Expected: Detect TypeScript, propose AGENTS.md as a map, docs/ECL.md, docs/STATUS.md,
architecture/development docs, changes active/parking/archive, generated INDEX.json workflow,
lint-ecl, lint-encoding, and package script or Makefile verification without writing business code.

## Prompt 2: Audit Partial Harness

```text
Use ecl-harness-engineer to audit a project that already has AGENTS.md and docs/ARCHITECTURE.md,
but no harness/changes and no lint-ecl. Return the gaps and priorities first.
```

Expected: Treat as Partial Harness/ECL Missing or Partial, identify missing ECL docs/scripts/templates,
preserve existing docs where possible, and avoid overwriting without delta review.

## Prompt 3: Personal Change Tracking

```text
Use ecl-harness-engineer to add personal-development change tracking to a small project:
single active task, parking/archive, and automatic INDEX.json generation.
```

Expected: Recommend the summary/spec/plan/tasks/reviews change template, single-active rule, docs/STATUS.md handoff,
script-generated INDEX.json, explicit park/close/resume transitions, and hook/CI validation
without automatic doc mutation.

## Prompt 4: Resume Recent Work

```text
Use ecl-harness-engineer to explain how an agent should resume recent work in a project with
docs/STATUS.md, no active change, and several archived changes in harness/changes/archive.
Which files should be loaded first, and should the full archive be read?
```

Expected: Load AGENTS.md and docs/ECL.md first, then docs/STATUS.md because no active change
exists. Use the STATUS archive path or INDEX.json to select history, start with archived
summary.md only, and do not load the full archive by default.

## Prompt 5: Active Change Overrides STATUS

```text
Use ecl-harness-engineer to define context loading for a project that has both docs/STATUS.md and
harness/changes/active/summary.md. Which source controls the current task?
```

Expected: Active change controls the current task. Read active summary/spec/plan/tasks/reviews before
task-specific docs. STATUS is not authoritative while active exists.

## Prompt 6: Core Harness Must Not Create Advanced Empty Directories

```text
Use ecl-harness-engineer to create a harness for a normal existing TypeScript project. The user wants
agent onboarding, ECL change tracking, lint checks, and CI only. List the directories you would
create under harness/.
```

Expected: Choose the core harness profile. Create `harness/config`, `harness/changes`, and
`harness/templates/change`. Do not create `harness/eval`, `harness/trace`, `harness/state`,
`harness/checkpoints`, `harness/memory`, or `harness/metrics`.

## Prompt 7: Explicit Advanced Eval Profile

```text
Use ecl-harness-engineer to add an agent evaluation framework to a project that already has the core
ECL harness. The user wants reusable eval prompts and benchmark datasets for testing agent
behavior over time.
```

Expected: Treat this as an advanced harness request. Load eval guidance, propose `harness/eval`
and datasets or prompt fixtures, define how evals are run and scored, and avoid touching unrelated
core ECL files except to link the eval workflow if needed.

## Prompt 8: Explicit Observability And Memory Profile

```text
Use ecl-harness-engineer to add trace logging and long-term agent memory to a project. The user wants
to debug long-running agent sessions and inspect recurring failures.
```

Expected: Treat this as an advanced harness request. Load observability and durability guidance,
define read/write protocols for `harness/trace` and `harness/memory`, include validation or
retention rules, and do not present these directories as normal day-one harness defaults.

## Prompt 9: Ordinary Business Feature Must Not Trigger Harness Creation

```text
Add a login button to this React app and wire it to the existing auth route.
```

Expected: Do not use ecl-harness-engineer. This is ordinary application feature implementation, not
harness creation or audit work.

## Prompt 10: Auto-Evolve Threshold Check Is Core

```text
Use ecl-harness-engineer to create a normal ECL harness. The project has no eval or memory request.
Should auto-evolve be included, and which files or scripts are part of it?
```

Expected: Include lightweight `harness/evolution/state.json`, `results.tsv`, `proposals/`, and
`scripts/harness-evolve.*` as core threshold-check infrastructure. Do not create `harness/eval`,
`harness/trace`, `harness/state`, `harness/checkpoints`, `harness/memory`, or `harness/metrics`.

## Prompt 11: Close Triggers Pending Evolution

```text
A project has 10 archived ECL changes and harness/evolution/state.json says the last evolution
processed 5 archives with threshold 5. What should the generated harness-change close command do after
moving the active change to archive?
```

Expected: Rebuild `INDEX.json`, run `harness-evolve check`, and generate
`harness/evolution/pending.md` if no pending file exists. The script must not directly edit
AGENTS.md, docs/ECL.md, STATUS, lint rules, or CI.

## Prompt 12: Pending Does Not Override Active Work

```text
The repository has both harness/changes/active/summary.md and harness/evolution/pending.md.
Which context should Codex handle first?
```

Expected: Active change remains authoritative. Read active summary/spec/plan/tasks/reviews first and
defer auto-evolve until the active change is closed or parked.

## Prompt 13: Darwin Ratchet For Harness Evolution

```text
Auto-evolve proposes a harness delta based on recent archives, but the new audit score is lower
and lint-ecl fails. What should happen?
```

Expected: Revert the auto-evolve delta, record `revert` in `harness/evolution/results.tsv`, keep
the proposal for audit, and do not advance `last_evolved_archive_count`.

## Prompt 14: No Independent Scorer Means Proposal Only

```text
Auto-evolve found a possible harness improvement, but this run has no available independent
auditor/subagent. Can Codex apply the delta automatically?
```

Expected: No. Generate and keep the proposal, mark `eval_mode=dry_run`, and do not auto-apply the
delta. Auto-apply requires independent scoring.

## Prompt 15: Independent Score Below Threshold

```text
The main auto-evolve flow rates a proposal at 84, but the independent auditor scores it 79 because
the evidence is weak. What should happen?
```

Expected: Reject the proposal before apply, record `rejected` in `results.tsv`, and leave harness
files unchanged.

## Prompt 16: Project-Irrelevant Candidate

```text
Auto-evolve proposes adding a broad prompt-engineering rule from an article, but no archived change
shows this project had that failure. The proposal otherwise looks reasonable.
```

Expected: Reject the candidate as project-irrelevant. It may stay in rejected candidates inside the
proposal, but must not enter AGENTS.md, ECL, STATUS, lint, or CI.

## Prompt 17: Accepted Candidate Requires Evidence And Target Files

```text
An auto-evolve proposal accepts a candidate but lists no archive summary and no target project files
or commands. Is it valid?
```

Expected: No. Accepted candidates require archived evidence and project relevance. Independent
review must return `rejected` or `noop`.

## Prompt 18: Small Change Skips Full ECL

```text
Use ecl-harness-engineer guidance for a project where the user asks: "Fix one typo in README.md."
Should the harness require a full active change with spec/plan/tasks?
```

Expected: Treat as Small Change. Do not require a full active change. The agent should make the
local fix, preserve unrelated files, and report the verification used.

## Prompt 19: Vague Requirement Needs Bounded Intake

```text
Use ecl-harness-engineer guidance for a user request: "Add a permissions module."
What should the agent do before generating implementation tasks?
```

Expected: Treat as Structured Change. Extract a draft `spec.md` and ask at most three high-impact
questions about users/scenarios, acceptance criteria, permissions/data boundaries, or compatibility.
Do not generate implementation tasks from the first vague requirement.

## Prompt 20: User Already Provided A Plan

```text
The user provides a detailed implementation plan for adding role-based access control, including
files to change and test commands. How should ecl-harness-engineer guidance handle this?
```

Expected: Treat the user plan as a draft input, not as final truth. Split WHAT/WHY into `spec.md`
and HOW into `plan.md`. If target users, acceptance criteria, non-goals, and verification are clear,
do not re-interview from scratch. If any high-impact gaps remain, ask only those questions.

## Prompt 21: Plan Missing Acceptance Criteria

```text
The user gives a plan with implementation steps for a search feature but no success metrics,
non-goals, or validation scenario. Can the agent proceed to implementation?
```

Expected: No. Record the missing acceptance and boundary information in `spec.md` as
`[NEEDS CLARIFICATION: ...]`, ask bounded high-impact questions, and block implementation until the
spec/plan gate is satisfied.

## Prompt 22: Planning Exposes A Spec Gap

```text
During draft planning, the agent realizes a proposed API change may require data migration and
backward compatibility decisions that were not in the spec. Where should this be recorded?
```

Expected: Record it in `plan.md` under `Spec Gaps Found From Planning`, add or update the related
open question in `spec.md`, and keep `plan_review` pending until resolved.

## Prompt 23: Boundary Check For Platform Scope

```text
Use ecl-harness-engineer to improve AI coding workflow. Should it create a Jira/Confluence sync,
a chat UI for requirements intake, or default eval/trace/memory directories?
```

Expected: No. Keep the skill scoped to harness creation/audit, ECL templates, scripts, lint gates,
and docs. Advanced platform directories or external sync only appear when explicitly requested.
