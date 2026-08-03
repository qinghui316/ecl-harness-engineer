# Existing Project Harness Update

## Purpose

Use `project migrate` to refresh project knowledge, install a supported runtime/schema revision, or
rebind a non-Git Harness after the project becomes Git-backed. Init and migrate use one bundle
validator and renderer.

## Inputs

- Project identity marker plus currently discovered Git/worktree facts.
- Current project Harness manifest, content, and dynamic state.
- A complete self-contained bundle for a full project knowledge refresh, containing four control
  files (`project-profile.json`, `architecture.json`, `audit.json`, and `creation-delta.json`) plus
  any artifact payloads named by the creation delta.
- Explicit authorization for executable creation-delta artifacts.

Ordinary project Harness documents, workflows, guides, and rules are edited directly in a
Structured Change. `project migrate` rejects focused document bundles with an instruction to use
that direct workflow.

Manifest `1.0` bootstrap state means `analysis_status` is absent, `bootstrap_only`, or `partial`; it
may receive the portable path upgrade without semantic invention. A `1.0` Harness with
`analysis_status: complete` must provide a new complete bundle; otherwise return
`semantic_refresh_required` (a full project knowledge refresh is required) and do not apply a
partial update.

## Invariants

- Preserve the opaque project id across directory moves and Git transitions.
- Persist only project-relative or Skill-relative paths.
- Remove project roots, Git common dirs, worktree paths, interpreter commands, runtime-link lists,
  and canonical-root fields from durable state.
- Preserve Change evidence, INDEX, contracts, baseline events, Integration results, and Evolution
  evaluated ids/results.
- Rebuild nonterminal Lane assignment from `project_id + branch`; never rewrite archived Change
  prose merely to change an owner id.
- Keep durable Integration Records under `state/registry/integrations/<integration-id>.json`; update
  each record's temporary worktree field to `state/integrations/<integration-id>`.
- Repository prose is analysis input, not complete-bundle or knowledge-index evidence.
- Knowledge scan/check remains read-only and cannot substitute for migration.
- A legacy `project_wiki/index.json` may be converted once without semantic reanalysis. The
  transaction adds generated-document frontmatter, imports knowledge source baselines, rebuilds the
  catalog, and removes the legacy index without changing document bodies or mutable state.
- This legacy conversion is the only `project migrate` path that omits `--analysis-bundle`.

## Transaction

1. Validate route identity, current state, bundle schema/evidence, protected paths, and path/link
   boundaries.
2. Build a staged migration candidate without mutable state and copy the supported Runtime from the
   currently executing ECL Harness Engineer Skill into it; do not preserve an older project Harness
   Runtime merely because it is installed.
3. Apply the complete bundle when a full project knowledge refresh is required, or perform only the
   explicit legacy index conversion when no analysis bundle is supplied.
4. Regenerate rules, catalog, and knowledge source baseline; validate the staged candidate.
5. Acquire the exclusive write lock, start the crash-recoverable transaction, and install the
   candidate without committing the transaction journal yet.
6. While the same command-level lock and journal remain active, repair current-machine links and
   bounded routes, normalize manifest, Git integration base, parallel work Lane, Change assignment,
   and Integration records to portable schema `2.0`, and retain mutable state.
7. Commit the transaction only after candidate content, portable state, links, and routes all pass;
   otherwise rollback content, state, and route changes together.

Any failure restores current content, state, and routes without leaving a mixed schema.

For an already Git-backed Harness, normalization preserves the recorded `canonical_branch` and
`canonical_commit`; it removes nonportable fields but does not advance the Integration base or emit
an advancement event. Only the non-Git-to-Git transition initializes missing baseline fields from
the named branch and current HEAD.

## Non-Git To Git

Never run `git init`. After Git exists on a named branch, keep the same physical Harness and project
id, replace `lane-single` with the branch-derived Lane, update nonterminal Change ownership, and
refresh source fingerprints using Git canonical blob semantics. Discover current and future
worktrees through Git and the connector; do not store their paths.

## Exit

Exit when one physical Harness remains, current links resolve to it, durable JSON contains no
machine-specific absolute paths, self-contained knowledge passes, and preserved state retains the
same business history and commit evidence.
