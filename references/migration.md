# Existing Project Harness Migration

## Purpose

Use `project migrate` to install the supported Runtime, schema, and shared templates in an existing
project Harness. Migration preserves project knowledge and mutable Change, Registry, Integration,
and Evolution state. It is not a project-analysis or knowledge-refresh command.

Use a normal Structured Change for current, target, decision, guide, workflow, or project-rule
content. Use E1 for cross-Change knowledge and rule improvement. Use `project init` only when no
project Harness exists.

## Inputs

- Project identity marker and current Git/worktree facts.
- Existing project Harness manifest and mutable state.
- Runtime and templates bundled with the currently executing ECL Harness Engineer Skill.

An existing-project migration rejects `--analysis-bundle`. It does not run the extractor,
Analyzer, Auditor, Creator, renderer, independent reviewer, or project test suite.

## Preserved State

- Keep the opaque project id and analysis status.
- Preserve every project Wiki document body, ID, layer, kind, status, knowledge owner, module, and
  evidence declaration.
- Preserve Change evidence and INDEX, coordination Registry contracts and events, Integration
  records, Evolution windows/results, and project Skill Git sidecars.
- Persist only project-relative or Skill-relative paths.
- Rebind nonterminal Lane ownership only when a schema or Git-mode transition requires it.

## One-Time Knowledge Conversion

Migration converts the retired `managed_by: renderer` marker to `managed_by: agent`. The conversion
changes only that frontmatter field, then updates document content digests and the generated
Catalog. Existing source fingerprints remain unchanged so migration cannot erase an unresolved
source-drift signal.

A legacy `project_wiki/index.json` is also converted once: missing mechanical frontmatter is added,
source fingerprints are imported into `.ecl-baselines.json`, `catalog.md` is generated, and the old
index is removed. Document bodies are not regenerated. `doctor` reports either legacy format and
recommends migration; it never modifies knowledge automatically.

## Transaction

1. Validate project identity, manifest schema, physical paths, links, and exclusive-writer state.
2. Copy current non-state Harness content into a staged migration candidate.
3. Replace the bundled Runtime and shared Runtime references in the candidate.
4. Perform legacy index and renderer-ownership conversions when present.
5. Rebuild the Catalog and baseline metadata, then run mechanical knowledge validation.
6. Compute the exact managed-file differences and apply them through the crash-recoverable file-set
   transaction while leaving mutable state and repository sidecars in place.
7. Repair discovery links and portable Registry paths, increment `skill_revision`, and commit the
   transaction.

Before the transaction enters `committing`, a failure restores content, manifest and mutable state
snapshots, routes, and newly created links. After `committing`, content and terminal state are kept
together and recovery only finishes candidate, backup, journal, and completion-marker cleanup. No
partial migration is reported as successful.

The transaction never renames the project Harness root. Each changed file is written through a
same-directory temporary file, flushed, and atomically replaced. The external recovery journal
stores affected-file backups and progress so the next Runtime command can rollback an interrupted
update. Ordinary Retire operations may leave empty directories; only an explicit file/directory
path conversion removes a required empty directory. Runtime commands wait for the filesystem
operation lock, and direct filesystem readers must not scan Harness content during migration.

## Acceptance

- Runtime/schema/templates match the current ECL distribution.
- Project knowledge bodies and semantic metadata are unchanged except the explicit ownership
  conversion.
- Catalog and source baseline are valid; old source fingerprints survive ownership conversion.
- Change, Registry, Integration, Evolution, project id, and Git-sharing state are preserved.
- `project doctor`, targeted knowledge check, rule views, and route checks are healthy apart from
  separately reported pre-existing findings.
