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
`project doctor` derives staleness from worktree existence, branch, commit, and record timestamps.

Store complete Change documents in the same physical Skill under
`state/changes/active|parking|archive/<change-id>/`. Rebuild `state/changes/INDEX.json` from Change
records and summaries after every lifecycle transition. Default context reads INDEX and a selected
summary; detailed spec/plan/tasks/review remains available for resume, review, failure analysis,
Integration, or Evolution without entering business Git.

## Lane Record

A Lane record contains `lane_id`, `worktree`, `branch`, `head_commit`, `active_change_id`, `status`,
and `updated_at`. One long-lived Lane may complete Changes sequentially.

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

In Git mode, close is deliberately two-stage. The first close validates project Harness evidence and
sets `closing`. The Worker commits the business implementation, then reruns close with the exact
clean HEAD and passing validation. The CLI binds that commit to the Change record, moves Skill
evidence to archive, and rebuilds INDEX. Change evidence itself never enters business Git.

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
Lane.

Treat every external Change, contract, and Integration id as untrusted input. Canonicalize and
validate it before deriving a path, reject separators/traversal, and require every loaded record id
to match its filename. Claim a new Change id with exclusive create, then create branch artifacts;
on failure remove only artifacts owned by that claim. Git Change creation requires a clean
worktree, and a terminal or closing Change cannot be reopened by publish.

Compare Change base and canonical baseline by Git ancestry: `equal`, `lane_ahead`,
`canonical_advanced`, or `diverged`. A plain hash mismatch is not enough to claim canonical
advancement.

## Integration

Integration begins only after a user requests it.

1. Create an Integration Record from selected completed Change ids.
2. Verify each exact completion commit and dependency.
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
10. Remove the temporary worktree only after Registry commit. Release the writer only after cleanup
    and the terminal Integration record are durable.

If cherry-pick conflicts, record the conflicted and remaining commits. After resolving and running
`git cherry-pick --continue`, use `integrate status --resume` so the same Integration Record applies
the remaining range before review.

An Integration Record is audit evidence, not a Change and not evolution-counted. Record conflicts,
extra Integrator edits, validation failures, human corrections, and documentation drift as signals
for the next five-Change window.

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
  contracts/events, shared current Change evidence, canonical code/documents, then periodic L1/L2/L3.

Do not maintain separate Harness versions per Lane.
