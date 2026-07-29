# Existing Project Harness Update

## Purpose

`project migrate` updates an existing project Harness with the same profile/audit/delta
renderer used by init. Its scope is the project Harness plus its managed routes, connector,
and local exclusion entry.

Use migrate when:

- an existing project Harness needs a fresh complete semantic bundle;
- the project changed enough to revise L1/L2/L3, workflows, rules, templates, or checks outside the
  normal five-Change Evolution cadence by explicit user request;
- a non-Git single-Lane project became Git-backed and must attach existing/future worktrees;
- the project Harness schema or runtime assets need an atomic supported update.

## Inputs

- Current project identity and Git common-dir/worktree facts.
- Complete evidence-backed `project-profile.json`, `architecture.json`, `audit.json`, and
  `creation-delta.json`.
- Current project Harness manifest/content and dynamic state.
- Explicit executable-artifact authorization when the delta contains executable files.

## Invariants

- Init and migrate use the same bundle validation and renderer.
- Build and validate a complete non-state candidate before publication.
- Preserve current `state/changes`, Change INDEX, Registry, evolution evaluated IDs/results, and
  in-flight ownership records.
- Artifact merge means the bundle supplies the complete merged candidate file, not an append.
- Knowledge comes from the profile; workflow/rule/template/check artifacts come from the delta.
- Knowledge scan/check remains read-only and cannot substitute for migrate.
- Existing business code/documents are evidence and stay canonical in Git.
- Repository writes remain limited to managed routes/connectors and local project Harness exclusion.

## Transaction

1. Validate project identity, bundle schemas, non-empty evidence, artifact target allowlist, and
   symlink/path boundaries.
2. Copy current non-state Skill content into a temporary candidate.
3. Apply the same profile/delta renderer used by init.
4. Regenerate rule views and Wiki index; run candidate knowledge, stage, doctor, artifact, and
   declared project checks.
5. Acquire the shared writer and short publication lock.
6. Publish the candidate as one recoverable root transaction while moving current dynamic state
   into the new root.
7. Repair all existing worktree links/routes, update manifest revision/runtime facts, and remove
   temporary transaction material.

Any failure restores current content and state, retains diagnostics, and never leaves a mixed root.

## Single-Lane To Git Upgrade

Derive the new identity from Git common dir, copy the existing physical Skill, preserve all Change
history/INDEX/evolution state, attach every detected worktree, install the host-native future
worktree connector, update baseline, and remove only old links that resolve to the predecessor.
Never run `git init` automatically.

## Exit

Exit when one physical Skill remains, all runtime links resolve to it, dynamic state is unchanged
except intentional manifest/baseline updates, and the new semantic projection passes.
