# Project Harness Architecture

## Responsibility Boundary

Create one project Harness per project. It stores complete AI-facing project knowledge, rules,
workflows, Change history, contracts, Integration results, and Evolution experience. Accepted code
and optional human-facing project documentation remain in the project repository, but repository prose
is not a runtime knowledge dependency.

All local worktrees and supported coding runtimes read one physical Harness. Machine facts such as
absolute paths, Git common dir, interpreter, links, and temporary processes exist only while a
command runs.

## Stable Identity

Create `project_id` once as `<project-slug>-<random-id>`. Treat it as opaque and preserve it across
directory moves, clones, non-Git-to-Git transitions, and migrations. Never derive or validate it
from an absolute project path or Git common dir.

Write the project id marker in the bounded AGENTS/Claude route. Discover an existing Harness from
that marker and verify both manifest id and Skill directory name. A same-named checkout without a
matching marker cannot claim the Harness.

## Physical Layout And Links

Place the physical Harness at:

```text
<primary-worktree>/.agents/skills/<project-id>-harness/
```

For a non-Git project, use the project root as the primary-worktree equivalent. Expose the same
physical directory in every current worktree at:

- Codex: `<worktree>/.agents/skills/<project-id>-harness`
- Claude Code: `<worktree>/.claude/skills/<project-id>-harness`

Use a directory junction on Windows and a relative symlink when practical on POSIX. Add exact local
Skill paths to Git common `info/exclude`; do not alter `.gitignore` only for local Harness storage.

The tracked connector discovers the current Git primary worktree, reads the project marker, finds
the matching physical Harness, and creates only the current worktree links. It rejects path escape,
identity mismatch, and existing-content collision. `project doctor --repair-links` diagnoses all
current worktrees and repairs local links without storing a link inventory.

Before removing a secondary worktree, run that worktree's connector in detach mode. The connector
prevalidates both Codex and Claude paths against the marked physical Harness, removes only matching
link nodes, and refuses physical content or a different target. Missing links are idempotent. Never
detach the primary worktree path that physically owns the project Harness.

Integration teardown follows one order: verify the shared target, detach both links, reject any
remaining unknown Windows directory Junction, then use non-force `git worktree remove`. A failed
verification or cleanup leaves the worktree available for diagnosis and retry.

## Portable Manifest

`state/manifest.json` uses schema `2.0`:

```json
{
  "schema_version": "2.0",
  "project_id": "repo-a1b2c3d4e5f6",
  "project_name": "repo",
  "skill_name": "repo-a1b2c3d4e5f6-harness",
  "skill_revision": 1,
  "analysis_status": "complete",
  "launchers": [],
  "created_at": "RFC3339 timestamp",
  "updated_at": "RFC3339 timestamp"
}
```

Do not persist project roots, Git common dirs, worktree addresses, interpreter commands, runtime
links, or canonical-root paths in manifest, Registry, INDEX, knowledge baseline, or generated history.
Project, Skill, Change, contract, and Integration paths are project-relative or Skill-relative.

Resolve the current interpreter when a launcher executes. PowerShell, Node, and Python connectors
remain independent pre-discovery host entries, not separate coordination implementations.

## Parallel Work Lane Discovery

Use `lane-single` outside Git. In Git, use `lane-<hash(project_id + branch)>`. Resolve current
worktree locations through Git and do not persist them. Detached HEAD may read knowledge and history
but cannot create Structured Changes because it has no stable branch Lane.

On a new machine, place the matching project Harness beside the project, retain the marker and
project ID, and rediscover current worktrees and links. Same-machine worktrees share the coordination
Registry and exclusive write locks; no cross-machine live coordination is implied.

## Knowledge Independence

Analyzer may read README, docs, and ADRs as temporary leads. Verify claims against code, manifests,
interfaces, configuration, tests, accepted contracts, or explicit user evidence, then write the
result completely into L1/L2/L3 and Architecture. Final analysis state and knowledge baselines do not
persist repository prose paths. Unknown claims remain unknown instead of being replaced by links.

Reference-source maps are different: they identify an inspected source checkout and commit, cite
reference-relative source files, and connect those facts to target L2/L3 maps. Default checkouts use
`.agents/reference-projects/<id>`; external checkout paths are analysis-time facts only.

## Repository Touchpoints

Keep repository integration bounded:

- managed route blocks in `AGENTS.md` and `CLAUDE.md`;
- one selected `scripts/harness-skill-link.*` connector;
- local Git common exclude entries;
- normal business code, tests, CI, and documents created only through accepted Changes.

Do not create repository Harness state as an initialization side effect.

## Optional Project Skill Git Repository

The project Harness includes an on-demand Git collaboration reference, but remains a local
physical directory by default. Only an explicit sharing request turns that directory into an
independent nested Git repository. The business repository excludes the whole project Skill through
its Git-common local exclude; the inner repository excludes dynamic state except the portable
manifest. Neither repository owns or tracks the other's operational state.

Repository metadata such as `.git`, `.gitignore`, README, and GitHub templates is outside stable
Harness content transactions. Migration and Evolution preserve it without copying it into staged
candidates or content digests. Same-machine business worktrees share one physical project Skill and
therefore one inner Git working tree.

## Failure And Migration

Initialization and migration apply updates through the existing recoverable content transaction. Preserve all
pre-existing routes and collisions. Remove only links created by the failed operation.

Migration from manifest `1.0` keeps the opaque project ID, removes machine fields, normalizes
parallel work Lane assignments and Integration paths, and preserves Change/INDEX/Registry/Evolution state. A complete old
Harness with repository-prose knowledge dependencies requires a new complete self-contained bundle;
otherwise return `semantic_refresh_required` (full project knowledge refresh required) without
applying a partial update.

Non-Git-to-Git transition never runs `git init`. Once Git exists, migrate Lane assignment to the
current named branch and refresh mechanical source fingerprints without changing semantic content.
