# Local Coordination And Integration

## Shared Coordination Registry

Store Registry records below `state/registry/`:

```text
baseline.json
lanes/<lane-id>.json
changes/<change-id>.json
contracts/<change-id>.json
integrations/<integration-id>.json
locks/evolution-owner/
```

`state/registry/integrations/<integration-id>.json` is the durable Integration Record.
`state/integrations/<integration-id>/` is the temporary Integration worktree; it is not a second
record store.

Use one file per Registry record and replace each file atomically. Do not require a daemon,
heartbeat loop, or shared chat.
`project doctor` maps recorded branches to the current `git worktree list` and uses branch, commit,
and record timestamps for diagnostics. Worktree locations are current-machine facts, not Registry
fields.

Store complete Change documents in the same physical Skill under
`state/changes/active|parking|archive/<change-id>/`. Rebuild `state/changes/INDEX.json` from Change
records and summaries after every lifecycle transition. Default context reads INDEX and a selected
summary; detailed spec/plan/tasks/review remains available for resume, review, failure analysis,
Integration, or Evolution without entering the project repository.

## Parallel Work Lane Record

A parallel work Lane record contains `lane_id`, `branch`, `head_commit`, `active_change_id`,
`status`, and `updated_at`. The `branch` field is the only persisted branch reference for a Lane.
One long-lived Lane may complete Changes sequentially. A parked Change may transfer to another Lane
through resume; preserve its existing Git base, or bind the current HEAD when a non-Git Change first
enters Git.

## Change Record

A Change record contains:

```text
change_id, lane_id, status, scope, paths,
base_commit, completion_commit, validation,
validation_passed, evidence_complete,
contract_required, contract_path, evidence_paths,
integration_status, integrated_by, created_at, updated_at
```

Allowed terminal statuses are `completed`, `blocked`, and `abandoned`. Only completed, validated,
evidence-complete Changes are evolution-eligible.

Status `blocked` is terminal: the accepted scope could not complete because of an external decision
or dependency. Use `parking` when the same Change is expected to resume.

`change new` creates status `planning`; `change publish --status active` records implementation in
progress. Both statuses hold path and contract claims. Parking and every terminal status release
those blocking claims.

Terminal records and archives remain historical evidence. Describe any follow-up relationship in
the new Change documents rather than rewriting the archived record.

Close is one-stage and does not require Git cleanliness or a commit. An existing linear completion
commit may be recorded as optional metadata. Integration later obtains an exact boundary from that
field or from its own `--completion-commit <change-id>=<sha>` input. Change evidence itself never
enters the project repository.

## Contract Record

Require a contract when work adds or changes an API, schema, event, configuration key, permission,
or module boundary. Record:

- Kind and stable subject id.
- Owning module and affected paths.
- Intended add/change/remove operation.
- Consumers and dependencies.
- Compatibility expectation and migration note.
- Evidence source and current status.

Change-to-Change dependencies use one explicit `change_dependencies` array. Each edge has exactly
one meaning:

```yaml
change_dependencies:
  - change_id: schema-implementation
    kind: integration
  - change_id: architecture-approval
    kind: evidence
    required_status: completed
    require_validation_passed: true
    require_evidence_complete: true
```

An `integration` edge controls Git ordering. Its Change must be selected in the same Integration or
already belong to a completed Integration Record. A selected Integration Change requires an exact,
non-empty, linear `base_commit..completion_commit` range.

An `evidence` edge is a semantic approval or evidence prerequisite. It never enters Git ordering,
cycle detection, range calculation, cherry-pick, or `integrated_by` updates. Runtime verifies the
exact Change identity, completed status, passing validation, complete archived evidence, and the
current content digests of its Change record, archive, and optional contract.

Reject duplicate ids, unknown dependency kinds, incomplete evidence policies, and contracts that
contain both `change_dependencies` and the historical `depends_on_changes` field. Do not infer a
kind from commit metadata, paths, or prose.

Terminal Change and contract records are immutable. To classify an existing historical
`depends_on_changes` declaration, create one new `dependency_classification` contract with
`operation: classify`, `status: accepted`, `classifies_change_id`, explicit
`change_dependencies`, and authorization evidence. Its owning correction Change must be completed,
validated, and evidence-complete. The classified dependency id set must exactly equal the legacy id
set, and exactly one correction contract may target that Change. Do not rewrite the historical
record, fabricate Git metadata, or silently remove an edge.

Preflight detects path overlap, same-subject contract overlap, dependency on a changing subject, and
Git integration-base advancement. It reports facts and required action; it does not auto-stop an
unrelated parallel work Lane. Planning and active Changes hold blocking claims. A completed,
non-integrated overlap is
reported separately as historical context so it can inform review without reserving paths or
contracts forever.

Treat every external Change, contract, and Integration id as untrusted input. Canonicalize and
validate it before deriving a path, reject separators/traversal, and require every loaded record id
to match its filename. Claim a new Change id with exclusive create, then create branch artifacts;
on failure remove only artifacts created for that Change ID. A terminal Change cannot be reopened
by `change publish`. Dirty worktree content is an Agent scope question, not a Change lifecycle
failure.

Compare recorded and current commits by Git ancestry: `equal`, `canonical_advanced`,
`worktree_behind`, `diverged`, `unavailable`, or `not_applicable`. Normal canonical advancement is
informational; divergence or an unavailable commit requires repair. A plain hash mismatch is not
enough to claim Git divergence.

## Integration And Integration Approval

Integration begins only after a user requests it.

The canonical branch is the project-level Integration target recorded in
`state/registry/baseline.json`; it is not selected separately for each Integration. Initialization
or an explicit project migration establishes it. Its recorded canonical commit is the Integration
base. Before landing, the runtime requires that branch's primary worktree to be
clean and its HEAD to equal either the recorded base or the already-landed reviewed commit. Landing
uses `git merge --ff-only <reviewed-commit>`; any other target-branch advancement rejects the
operation instead of overwriting or merging it.

1. Resolve every selected Change and its explicit dependency classifications before creating an
   Integration Record or temporary worktree. Reject missing, duplicate, ambiguous, mismatched, or
   unsatisfied dependencies without leaving either artifact behind.
2. Resolve each exact completion commit from optional Change metadata or Integration input. Build
   the topological order only from `kind: integration` edges. A dependency not selected in the same
   Integration must already be bound to a completed Integration Record. Evidence edges do not enter
   the Git graph or Git cycle detection.
3. Create a temporary worktree from the canonical commit recorded in the coordination Registry.
4. For each Change, verify a linear `base_commit..completion_commit` range and cherry-pick that
   exact range in dependency order. Never merge the full tip of a long-lived Lane.
   Git ancestry proves range shape, not semantic ownership; the Change author and Integrator must
   also verify that the range contains no unrelated commits.
5. Let the Integrator resolve conflicts and edit the combined result as in a local PR, including
   authoritative project documentation tracked in the repository.
   This means tracked documentation in the project repository, never project Harness L1/L2/L3 or
   other Harness references.
6. Store dependency declaration and authorizing Change-evidence snapshots, separately list
   `satisfied_evidence_dependencies`, and bind their SHA-256 content digest in the Integration Record. After all candidate edits, run
   contract review, aggregate tests, and independent review; bind that review to both the exact
   candidate commit and `dependency_binding_digest`. Any later candidate or dependency-evidence
   change requires repeating validation and review.
7. Present the combined diff, verification, and risks for integration approval (I2).
8. After I2, revalidate the structured `--review-report` presented for approval: its reviewed commit
   must equal the current Integration HEAD, its dependency digest must equal the staged record, and
   its reviewer must differ from the Integrator. Acquire the exclusive write lock, recompute every
   evidence and classification digest before landing, then advance through
   recoverable `pre_merge`, `canonical_landed`, `registry_committed`, and
   `cleanup_complete` phases. Record full contract snapshots, previous/new canonical commits, and
   affected paths in `canonical-baseline-advanced`. Do not rewrite L1/L2/L3.
9. Remove the temporary worktree only after Registry commit. First verify and detach its Codex and
    Claude links to the shared project Harness, then reject unknown directory Junctions and run
    non-force `git worktree remove`. Release the exclusive write lock only after cleanup and the
    terminal Integration record are durable.

Phase persistence is write-ahead only for `pre_merge`: record it before `merge --ff-only`.
Record `canonical_landed` only after target HEAD equals the reviewed commit, `registry_committed`
only after baseline/events/Change records are durable, and `cleanup_complete` only after link and
worktree cleanup. Retry checks both the recorded phase and observed target HEAD before continuing.

If cherry-pick conflicts, record the conflicted and remaining commits. After resolving and running
`git cherry-pick --continue`, use `integrate status --resume` so the same Integration Record applies
the remaining range before review.

An Integration Record is audit evidence, not a Change and not evolution-counted. Record conflicts,
extra Integrator edits, validation failures, human corrections, and documentation source changes as
evidence for the next set of five Changes reviewed by Evolution.

The Integration Record's `change_ids`, `completion_commits`, and `change_commit_ranges` contain only
selected Git Integration Changes. `satisfied_evidence_dependencies` is a separate immutable
snapshot for evidence-only prerequisites; registry commit must not set `integrated_by` on those
Changes.

The same teardown protects `integrate complete` and `integrate abort`. A cleanup failure keeps the
record and exact failure path for retry; it must not repeat canonical landing or Registry writes.
`integrate abort` is allowed only before canonical landing. After landing, forward recovery through
`integrate complete` is required; abort never rewinds the canonical branch.
For a user-managed secondary worktree, run the tracked connector with `--detach` (or `-Detach` for
PowerShell) before `git worktree remove`.

Reviewer identity is a cooperative local-agent separation gate, not cryptographic authentication.
The candidate commit SHA, report fields, and identity mismatch are mechanically enforced;
deployments
that require adversarial identity proof need a separate trusted review system outside this scope.

## Git Integration-Base Advancement

Keep these commits distinct:

- Change `base_commit`: the Lane commit where one Change began.
- Change `completion_commit`: the optional end of that Change's selected range.
- Registry `canonical_commit`: the recorded commit of the Integration target branch, used to create
  the temporary Integration worktree and detect target-branch advancement.

“Integration-base advancement” refers only to movement from the recorded Registry
`canonical_commit`; it does not replace a Change's `base_commit`.

All parallel work Lanes see shared knowledge and coordination Registry updates immediately. At
preflight:

- Read integration-base events since the Change base, plus related knowledge source changes.
- Continue when the new integration base does not invalidate the accepted Change contract or
  claimed paths.
- Rebase or merge when required by project policy.
- Pause and re-plan when an API, schema, permission, safety rule, or required dependency changed.
- Return `knowledge.status=refresh-needed` for an affected scope. When facts conflict, use
  the coordination Registry for integration-base and contract coordination, the current Change for
  accepted scope, repository code/manifests/configuration/tests/interfaces for implemented
  behavior, and periodic L1/L2/L3 for project context.

Do not maintain separate Harness versions per Lane.
