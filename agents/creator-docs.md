# Documentation Creation Agent

Create the project-specific knowledge, workflows, rules, and Change templates for one shared local
project Harness. Apply the complete ECL behavior through its current owners and progressive reading paths.

## Inputs

- Validated `project-profile.json` with purpose, flows, modules, commands, environment,
  bridges, boundaries, unknowns, and evidence.
- `audit.json` with semantic gaps, drift, duplication, and enforcement findings.
- Shared `creation-delta.json` plus its artifact directory.
- Current project Harness content when updating through migrate or E1 Evolution.

## Output Boundary

Create semantic artifacts only below the project Harness:

```text
SKILL.md
references/project_wiki/
references/workflows/
references/rules/red_lines.yaml
assets/templates/
```

The CLI owns deterministic Wiki rendering from the profile, generated indexes, rule views, links,
Registry state, and atomic publication. Creator artifacts may replace or merge complete candidate
files only when `creation-delta.json` names their owner, evidence, action, and validation.

The business repository owns product code and optional human-facing documents. Write verified
AI-facing knowledge completely into the project Harness; repository prose is not a required link
or durable evidence source. Repository writes are limited to the bounded
managed AGENTS/Claude route and selected worktree connector installed by the CLI.

## Project Harness Entry

Keep project Harness `SKILL.md` a concise stage router. It must identify:

- project id and local-only boundary;
- default context order;
- Small versus Structured Change trigger;
- command surface;
- stage workflow links;
- an on-demand route to project Skill Git collaboration guidance;
- stable ownership and current-fact precedence;
- I2 for canonical Integration and E1-only Evolution.

Do not place module catalogs, Change history, full rules, environment setup, or command explanations
in the entry file.

Generate `references/git-collaboration.md` for optional independent distribution of the project
Skill. It is guidance, not an initialization action: project creation must not run `git init`, add a
remote, commit, or push. The route is loaded only for project Skill sharing, clone, update, PR, or
Git-boundary diagnosis.

## L1 Overview

Render `references/project_wiki/overview.md` from profile evidence. Scale it to project complexity
without a fixed byte or line limit, and include:

1. Project purpose and primary user/system flows.
2. Major modules with one-sentence responsibilities and L2 links.
3. Configured command and verification entrypoints.
4. Global boundaries that affect most work.
5. Explicit unknowns that materially limit planning.

Exclude Lane status, active Changes, archive ledgers, full directory trees, and historical
narrative. Preserve every project-level navigation link an Agent needs by default; move module
detail to L2/L3 instead of truncating the map. L1 is a periodic map, not the newest fact owner.

## L2 Systems And Designs

Create module pages only when manifests, imports, entrypoints, tests, interfaces, or contracts
prove a coherent owner. L2 also holds accepted target architecture and important design/domain
documents. Each page includes responsibility, roots, entrypoints,
interfaces/data owners, dependencies, tests, commands, boundaries, citations, and source
fingerprints. A top-level directory name alone is never enough.

Use indexed ECL frontmatter for Agent-owned current, target, decision, and guide documents. The
semantic layer comes from impact and reading depth, not a filename or fixed subdirectory. Never
present an unimplemented target as current architecture.

Render command, environment, and verification system pages with detail supported by project evidence.
Unknown values stay explicit. Do not invent a technology, service, port, readiness endpoint, or
command merely to fill a page.

## L3 Contracts And Semantic Bridges

Use L3 for precise interfaces, schema, events, call flows, implementation standards, and proven
translation boundaries. Create a bridge only for a proven translation boundary:

- product terminology to code owner;
- API/schema/event/config field to module;
- UI/read-model/component name to implementation;
- provider/runtime adapter to boundary;
- design token to project API.

Every mapping cites source code, manifest/configuration, tests, an integrated contract, or an explicit
user statement. Search synonyms may locate candidates but never establish durable truth.

## Reference Project Source Maps

When the approved profile contains reference projects, render
`references/project_wiki/reference_projects/index.md` plus one source map under `maps/` for each
analyzed checkout. The index is navigation for direct reference research. It is not a runtime gate.

Write the actual relationship into the relevant project knowledge:

- L1 mentions only a reference foundation that affects the whole project.
- L2 module pages identify the referenced mechanism, adaptation, boundaries, validation, and map.
- L3 mappings connect a referenced interface/schema/event/runtime concept to the target owner.

The reference map records source, checkout identity, inspected commit, inspected files, modules,
interfaces, call paths, tests, evidence, license evidence, and unknowns. Keep reference facts out of
target commands, environment, CI, dependencies, and module ownership.

## Mature ECL Workflows

Generated workflows implement the complete process and use the common stage contract: Inputs, Agent
Judgment, Deterministic Commands, Actions, Outputs, Exit, Stop And Escalate, and Rule IDs.

- Intake supports requirement-first, plan-first, and mixed input; asks at most three high-impact
  questions per round; records low-risk assumptions and blocks on unresolved high-impact facts.
- Locate uses the L1 -> candidate L2 -> deterministic search -> relevant source trace -> L3 funnel.
- Plan keeps WHAT/WHY in spec and HOW in plan, records planning-discovered spec gaps, maps each AC
  to owner/task/validation, and publishes high-impact contracts.
- Implement preserves scope, follows existing project patterns, and returns new failures to the
  Change instead of hiding them.
- Verify classifies introduced, pre-existing, environmental, and blocked failures and records
  command, working directory, exit result, and acceptance evidence.
- Close validates complete project Harness evidence, archives the Change in the Skill, and rebuilds
  INDEX without requiring Git; an optional boundary can be recorded for later Integration.
- Integrate applies selected exact commit ranges, permits Integrator corrections, runs aggregate
  validation/review, and waits for I2.
- Evolve freezes five qualified Changes after E1, performs Promote/Retain/Merge/Retire/Archive-only,
  applies only after independent score and validation gates, and has no E2.

## Change Templates

The project Harness owns complete Change evidence under `state/changes/active|parking|archive`.
Templates must preserve:

- `summary.md`: phase, outcome, scope, decisions, validation, risks, next step, handoff.
- `spec.md`: intake shape, goal/evidence, scenarios, ACs, non-goals, constraints, assumptions,
  unresolved and resolved clarifications.
- `plan.md`: technical approach, owners/paths, interfaces/data/permissions/contracts, spec gaps,
  risks/mitigations, validation plan, plan review.
- `tasks.md`: stable task ids, optional parallel marker, AC mapping, target owner/path, validation.
- `reviews/review.md`: intake/spec/plan/code/validation/contract/integration/knowledge/entropy review.

The generated `state/changes/INDEX.json` is machine-owned. Default context reads INDEX and a
selected summary; detailed files load only for resume, review, failure analysis, Integration, or
Evolution. Complete history remains available and is not copied into current rules or L1.

## Documentation Entropy

- One current fact has one owner.
- Entry files route; workflows instruct; rules constrain; Wiki maps; Registry coordinates; Change
  files explain one task; archive preserves history.
- Prefer editing an existing owner over adding a new file.
- Merge duplicate current facts and retire stale roadmap/baseline language.
- Keep closeout narrative in Change archive and load it selectively through INDEX.
- Line count is an alarm, not a quality score; compact content must still be specific and useful.

## Exit

Exit only when a fresh Agent can identify the project, choose the relevant module and workflow,
find current Change evidence, select configured validation, and avoid loading unrelated history.
Every durable claim has evidence, every created artifact has one owner, and no repository-owned
Harness structure is proposed.
