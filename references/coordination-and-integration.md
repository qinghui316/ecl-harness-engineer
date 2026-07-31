# Local Coordination And Integration

## Shared Registry

Store Registry records below `state/registry/`:

```text
baseline.json
lanes/<lane-id>.json
changes/<change-id>.json
contracts/<change-id>.json
integrations/<integration-id>.json
locks/evolution-owner/
```

Use one file per owner and atomic replace. Do not require a daemon, heartbeat loop, or shared chat.
`project doctor` maps recorded branches to the current `git worktree list` and uses branch, commit,
and record timestamps for diagnostics. Worktree locations are current-machine facts, not Registry
fields.

Store complete Change documents in the same physical Skill under
`state/changes/active|parking|archive/<change-id>/`. Rebuild `state/changes/INDEX.json` from Change
records and summaries after every lifecycle transition. Default context reads INDEX and a selected
summary; detailed spec/plan/tasks/review remains available for resume, review, failure analysis,
Integration, or Evolution without entering business Git.

## Lane Record

A Lane record contains `lane_id`, `branch`, `head_commit`, `active_change_id`, `status`, and
`updated_at`. One long-lived Lane may complete Changes sequentially. A parked Change may transfer to
another Lane through resume; preserve its existing Git base, or bind the current HEAD when a
non-Git Change first enters Git.

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

Terminal records and archives remain historical evidence. Describe any follow-up relationship in
the new Change documents rather than rewriting the archived record.

Close is one-stage and does not require Git cleanliness or a commit. An existing linear completion
commit may be recorded as optional metadata. Integration later obtains an exact boundary from that
field or from its own `--completion-commit <change-id>=<sha>` input. Change evidence itself never
enters business Git.

## Contract Record

Require a contract when work adds or changes an API, schema, event, configuration key, permission,
or module boundary. Record:

- Kind and stable subject id.
- Owning module and affected paths.
- Intended add/change/remove operation.
- Consumers and dependencies.
- Compatibility expectation and migration note.
- Evidence source and current status.

Preflight detects path overlap, same-subject contract overlap, dependency on a changing subject, and
baseline advancement. It reports facts and required action; it does not auto-stop an unrelated
Lane. Planning and active Changes hold blocking claims. A completed, non-integrated overlap is
reported separately as historical context so it can inform review without reserving paths or
contracts forever.

Treat every external Change, contract, and Integration id as untrusted input. Canonicalize and
validate it before deriving a path, reject separators/traversal, and require every loaded record id
to match its filename. Claim a new Change id with exclusive create, then create branch artifacts;
on failure remove only artifacts owned by that claim. A terminal Change cannot be reopened by
publish. Dirty worktree content is an Agent scope question, not a Change lifecycle failure.

Compare Change base and canonical baseline by Git ancestry: `equal`, `lane_ahead`,
`canonical_advanced`, or `diverged`. A plain hash mismatch is not enough to claim canonical
advancement.

## Integration

Integration begins only after a user requests it.

1. Create an Integration Record from selected completed Change ids.
2. Resolve each exact completion commit from optional Change metadata or Integration input, then
   verify the boundary and dependencies.
3. Create a temporary worktree from the Registry canonical baseline.
4. For each Change, verify a linear `base_commit..completion_commit` range and cherry-pick that
   exact range in dependency order. Never merge the full tip of a long-lived Lane.
5. Let the Integrator resolve conflicts and edit the combined result as in a local PR.
6. Run contract review, aggregate tests, and independent review; record the exact reviewed
   candidate commit.
7. Update accepted business documents in the integration candidate.
8. Present the combined diff, verification, and risks for I2.
9. After I2, require a structured `--review-report` whose reviewed commit equals the current
   Integration HEAD and whose reviewer differs from the Integrator, then advance through
   recoverable `pre_merge`, `canonical_landed`, `registry_committed`, and
   `cleanup_complete` phases. Publish full contract snapshots, previous/new canonical commits, and
    affected paths in `canonical-baseline-advanced`. Do not rewrite L1/L2/L3.
10. Remove the temporary worktree only after Registry commit. First verify and detach its Codex and
    Claude links to the shared project Harness, then reject unknown directory Junctions and run
    non-force `git worktree remove`. Release the writer only after cleanup and the terminal
    Integration record are durable.

If cherry-pick conflicts, record the conflicted and remaining commits. After resolving and running
`git cherry-pick --continue`, use `integrate status --resume` so the same Integration Record applies
the remaining range before review.

An Integration Record is audit evidence, not a Change and not evolution-counted. Record conflicts,
extra Integrator edits, validation failures, human corrections, and documentation drift as signals
for the next five-Change window.

The same teardown protects `integrate complete` and `integrate abort`. A cleanup failure keeps the
record and exact failure path for retry; it must not repeat canonical landing or Registry writes.
For a user-managed secondary worktree, run the tracked connector with `--detach` (or `-Detach` for
PowerShell) before `git worktree remove`.

Reviewer identity is a cooperative local-agent separation gate, not cryptographic authentication.
The candidate SHA, report fields, and identity mismatch are mechanically enforced; deployments
that require adversarial identity proof need a separate trusted review system outside this scope.

## Baseline Advancement

All Lanes see shared knowledge and Registry updates immediately. At preflight:

- Read baseline events since the Change base, plus related knowledge-source drift.
- Continue when the new baseline does not invalidate the accepted Change contract or claimed paths.
- Rebase or merge when required by project policy.
- Pause and re-plan when an API, schema, permission, safety rule, or required dependency changed.
- Return `knowledge.status=refresh-needed` for an affected scope. Current-fact priority is Registry
  contracts/events, shared current Change evidence, repository code/manifests/configuration/tests/interfaces,
  then periodic L1/L2/L3.

Do not maintain separate Harness versions per Lane.
