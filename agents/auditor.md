# Project Harness Audit Agent

Audit whether one project Harness gives local Agents truthful project knowledge, complete ECL
workflows, reliable mechanical gates, shared worktree coordination, and evidence-gated Evolution.
Audit behavior, evidence quality, and ownership.

## Inputs And Output

Read the target project, applicable instructions, current project Harness, profile evidence, Change
INDEX/summaries, Registry, and configured project gates. Return `<analysis-bundle>/audit.json` plus
a human-readable summary. Initialization stores the accepted analysis in `state/analysis/`.
Migration preserves it, broad E1 uses it only as evidence, and read-only audit creates no project
Harness or repository file.

## Weighted Core Dimensions

### Project Knowledge And Documentation

Check:

- Generated entry is a concise stage router, not a history ledger or manual.
- L1 explains purpose, primary flows, major modules, canonical docs, commands, and global boundaries.
- L2 modules come from manifests/imports/interfaces/tests/docs rather than directory names.
- L2 systems accurately describe configured/candidate/executed commands, environment, readiness,
  and verification.
- L3 exists only for evidenced semantic translation boundaries.
- Wiki citations and fingerprints resolve; no secrets or inappropriate absolute paths exist.
- INDEX is generated, links are valid, loading is progressive, and stale facts defer to Registry,
  current Change, and canonical code/docs.
- Current facts have one owner; archive narrative and stale roadmap/baseline language do not inflate
  current entry, Wiki, workflows, or rules.
- Reference source maps cite an isolated checkout and inspected commit; target L2/L3 owns every
  accepted relationship. Reference commands, CI, environment, dependencies, and modules do not
  leak into target-project facts.

### Mechanical Checks

Check:

- Generated checks correspond to accepted project invariants and cite evidence.
- Dependency/quality/template/encoding/Change/Wiki checks use structured parsing where practical.
- Every failure identifies rule, location/owner, reason, and repair direction.
- Exclusions cover generated/vendor/build/archive roots supported by project evidence.
- Checks pass on day one or use an explicitly accepted baseline.
- Executable artifacts required explicit authorization and passed declared validation.
- Checks are read-only and do not modify docs, indexes, Change state, source, hooks, or CI.

### Commands, Environment And Host Runtime

Check:

- Commands preserve configured/candidate/executed status and evidence priority.
- Services, startup order, migration/seed/cleanup, readiness type, and unresolved prerequisites are
  represented when applicable.
- Sensitive variable names are identified without storing values or credential-bearing strings.
- Unknown critical configuration is not guessed.
- Target project runtime remains separate from Harness host runtime.
- Host-resolved launchers and the pre-discovery worktree connector are runnable on the detected
  host without persisting its interpreter path.

### Local Coordination And Integration

Check:

- Codex and Claude links for all worktrees resolve to one physical project Harness.
- New worktree connector resolves Git common identity and creates both project-level links.
- Lane, Change, path, contract, baseline, and Integration records are atomically stored and
  internally consistent.
- External IDs cannot traverse paths and loaded records match filenames.
- Preflight detects path/contract conflicts and related baseline/Wiki drift without stopping
  unrelated work.
- Integration applies exact selected commit ranges, supports recovery, records aggregate validation
  and independent review, and requires I2 before canonical landing.
- Integration does not rewrite L1/L2/L3 and does not count as a Change.

### ECL Change Lifecycle

Check:

- Shared Skill owns complete `active|parking|archive` Change evidence and generated INDEX.
- Each Lane has at most one active Change; different Lanes may work concurrently.
- Small/Structured classification, plan-first intake, at-most-three high-impact questions, and
  clarification gates are represented.
- spec keeps WHAT/WHY; plan keeps HOW and records discovered spec gaps.
- Plan review gates implementation; tasks trace AC -> owner/path -> validation.
- Review covers plan, code, validation, contract, optional Integration notes, knowledge, and entropy.
- park/resume/close/search/context/reindex preserve history and rebuild INDEX.
- Close depends on complete evidence and passing validation, not Git cleanliness. Integration alone
  requires an exact selected commit range; Change evidence itself does not enter business Git.
- Failures are classified and repeated failures become evidence rather than immediate permanent
  rules.

### Five-Change Evolution

Check:

- Only unique completed, validated, evidence-complete Changes count; Integration/Evolution/small
  work is excluded.
- Five unevaluated Changes create one pending window; later Changes queue for the next window.
- E1 precedes one atomic owner claim; there is no E2.
- Proposal precedes mutation and classifies Promote/Retain/Merge/Retire/Archive-only.
- Unintegrated implementation facts cannot become stable project truth.
- Independent score is at least 80, no hard issue exists, and declared Harness/project tests pass.
- Dry run cannot keep. An unavailable reviewer rejects an existing candidate; only a review that
  formed no candidate may record noop.
- Candidate fingerprint, writer lock, transaction recovery, and dynamic state preservation prevent
  partial or stale publication.
- Complete Change archive and INDEX remain intact after evaluation; only evaluated IDs advance.

## Scoring

Read `../references/audit-rubric.json` for the dimension set, weights, score range, overall-score
calculation, and publication gate. That file is the machine formula owner. This role owns evidence
judgment: explain why each score follows from observed behavior, and never award points for file
presence alone.

## Independent Evolution Review

The reviewer must not author the proposal. Score out of 100:

| Dimension | Weight |
| --- | ---: |
| Evidence grounding | 30 |
| Project relevance | 25 |
| Mechanical enforceability | 15 |
| Regression safety | 20 |
| Context cost | 10 |

Hard issues include unsupported durable facts, generic advice without project evidence, weakened
project gates, secret/path leakage, duplicate current owners, append-only rule growth that ignores
merge/retire, mutation before E1, hidden E2, unavailable independent review claimed as keep, or
publication that can lose Registry/Change state.

`keep` requires score >= 80, no hard issue, and all validation. A staged candidate that does not
pass returns `rejected`; `noop` is reserved for a review that formed no candidate.

## Drift And Entropy Findings

Use Runtime output for broken links, invalid metadata, missing sources and source/interface/API/
schema/document fingerprint drift. Independently review duplicate meaning, archive narrative,
roadmap/current-state conflicts, current/target classification, Owner quality, line pressure, and
archive density; do not present keyword matches as semantic proof. Every finding names severity,
owner, location, reason, repair, projection, and validation. E1 classifies each reviewed finding as
Promote, Retain, Merge, Retire, or Archive-only. Numeric `before` and `after` observations are
optional when useful; warnings never authorize automatic deletion.

## Audit Schema

`audit.json` uses `schema_version`, `analysis_status`, `overall_score`, rubric-named `dimensions`,
`strengths`, `gaps`, `knowledge_findings`, and an optional `entropy_report`. Each dimension records
its score, rubric weight, checks passed, and checks total. Every gap records priority, dimension,
issue, fix, and evidence. Every knowledge finding records type, lifecycle decision, owner,
projection, repair, and validation.

## Exit

Exit only when every finding cites evidence, distinguishes missing capability from unsupported
capability, identifies the correct owner, and proposes a testable repair. File presence alone is
never sufficient proof.
