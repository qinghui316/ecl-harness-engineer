# Existing Project Harness Update

## Purpose

Use `project migrate` to refresh semantic content, install a supported runtime/schema revision, or
rebind a non-Git Harness after the project becomes Git-backed. Init and migrate use one bundle
validator and renderer.

## Inputs

- Project identity marker plus currently discovered Git/worktree facts.
- Current project Harness manifest, content, and dynamic state.
- A complete self-contained four-file bundle for semantic refresh:
  `project-profile.json`, `architecture.json`, `audit.json`, and `creation-delta.json`.
- Explicit authorization for executable creation-delta artifacts.

Manifest `1.0` bootstrap state may receive the portable path upgrade without semantic invention. A
complete `1.0` Harness must provide a new complete bundle; otherwise return
`semantic_refresh_required` and do not publish.

## Invariants

- Preserve the opaque project id across directory moves and Git transitions.
- Persist only project-relative or Skill-relative paths.
- Remove project roots, Git common dirs, worktree paths, interpreter commands, runtime-link lists,
  and canonical-root fields from durable state.
- Preserve Change evidence, INDEX, contracts, baseline events, Integration results, and Evolution
  evaluated ids/results.
- Rebuild nonterminal Lane ownership from `project_id + branch_ref`; never rewrite archived Change
  prose merely to change an owner id.
- Convert Integration worktree records to `state/integrations/<integration-id>`.
- Repository prose is candidate context, not complete-bundle or knowledge-index evidence.
- Knowledge scan/check remains read-only and cannot substitute for migration.

## Transaction

1. Validate route identity, current state, bundle schema/evidence, artifact allowlist, and path/link
   boundaries.
2. Build a non-state candidate and mirror the current Harness runtime into it.
3. Apply the complete bundle when semantic refresh is required.
4. Regenerate rules and knowledge index; run candidate checks.
5. Acquire the shared writer and publish through the recoverable content transaction.
6. Normalize manifest, baseline, Lane, Change owner, and Integration records to portable schema
   `2.0` while retaining dynamic state.
7. Repair current-machine links and bounded routes from live Git discovery.

Any failure restores current content, state, and routes without leaving a mixed schema.

## Non-Git To Git

Never run `git init`. After Git exists on a named branch, keep the same physical Harness and project
id, replace `lane-single` with the branch-derived Lane, update nonterminal Change ownership, and
refresh source fingerprints using Git canonical blob semantics. Discover current and future
worktrees through Git and the connector; do not store their paths.

## Exit

Exit when one physical Harness remains, current links resolve to it, durable JSON contains no
machine-specific absolute paths, self-contained knowledge passes, and preserved state retains the
same business history and commit evidence.
