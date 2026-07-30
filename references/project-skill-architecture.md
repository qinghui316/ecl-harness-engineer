# Project Harness Architecture

## Purpose

Create one local project Harness per project. All local worktrees and supported coding runtimes read
the same physical directory. The business repository remains responsible for accepted code and
business documents. The shared project Harness owns current and historical Change evidence.

## Identity

For a Git project, derive identity from:

1. Absolute normalized Git common dir.
2. Repository top-level name.
3. A stable twelve-character SHA-256 prefix of the normalized common-dir path.

Use `<repo-slug>-<hash>-harness` as the local project Harness directory name. All linked worktrees resolve to
the same common dir and therefore the same project id.

For a non-Git project, hash the normalized project root and set `mode` to `single_lane`.

Do not write the absolute identity path into repository-tracked files. It is local manifest state.

## Canonical Project-Level Layout

Resolve the Git primary worktree from the Git common dir. Create the one physical project Harness at:

```text
<primary-worktree>/.agents/skills/<project-id>-harness/
```

For a non-Git project, the project root is the primary worktree equivalent. Keep `state/` in the
same physical project Harness so every local runtime observes one Registry and one Evolution window.

This project-bound Harness is not installed in a global Skill directory. In Git mode, add the
exact Codex and Claude Harness paths to the Git common dir's `info/exclude`; do not change
the repository `.gitignore` solely for this machine-local asset.

## Runtime Discovery Links

For every linked worktree, expose the same physical project Harness at:

- Codex: `<worktree>/.agents/skills/<project-id>-harness`.
- Claude Code: `<worktree>/.claude/skills/<project-id>-harness`.

The primary worktree's Codex path is the physical directory. Every other path is a link named
exactly like that Harness. On Windows, use a directory junction. On POSIX, use a relative symlink
when possible.

Future worktrees cannot inherit untracked links from a branch. Therefore the repository route
includes one small tracked host-native connector: PowerShell on Windows when available, Node on
other supported hosts when available, and Python as a fallback. A fresh Agent reads the managed
AGENTS/Claude route, runs the connector when the project Harness is absent, then reloads it. It runs
preflight before planning or editing repository changes. The connector resolves the Git common dir/primary worktree and creates only the
current worktree's two project-level links. `project doctor --repair-links` repairs all detected
worktrees.

Before replacing a path:

- If it already resolves to the canonical project Harness, keep it.
- If it is an unrelated directory or link, stop and report the collision.
- Never merge two physical project Harness copies.

## Host Runtime

Keep the target application runtime separate from Harness execution. The Harness runtime's Python
helpers are the deterministic coordination implementation. During initialization, PowerShell or
POSIX launchers pin the actual interpreter used for that run in local-only Harness state; Windows
falls back to a `.cmd` launcher with the same pinned interpreter when PowerShell is unavailable. Generated
`SKILL.md` routes through those launchers instead of assuming the target project uses Python.

The tracked new-worktree connector must be runnable before the project Harness is discoverable.
Select PowerShell on Windows, Node when available on other hosts, and Python only as a supported
fallback. Never hardcode a Python-only bootstrap into `AGENTS.md` for a host that has a native
PowerShell or Node route.

## Manifest

Store `state/manifest.json` with this minimum schema:

```json
{
  "schema_version": "1.0",
  "project_id": "repo-slug-0123456789ab",
  "project_name": "repo-slug",
  "project_root": "local-only absolute path",
  "git_common_dir": "local-only absolute path or null",
  "mode": "multi_lane",
  "skill_revision": 1,
  "host_runtime": "python",
  "host_command": "local-only interpreter path",
  "created_at": "RFC3339 timestamp",
  "updated_at": "RFC3339 timestamp",
  "runtime_links": []
}
```

Allowed modes are `multi_lane` and `single_lane`. Never infer cross-machine coordination from
`multi_lane`; it means local linked worktrees only.

## Repository Touchpoints

Keep repository integration small:

- `AGENTS.md`: preserve existing content and maintain one bounded Harness route block.
- `CLAUDE.md` or existing Claude route: preserve existing content and maintain the same bounded
  route without duplicating the manual.
- `scripts/harness-skill-link.{ps1,mjs,py}`: one selected connector that bootstraps links in a new
  worktree; an unmanaged path collision is fatal.
- Project Harness `state/changes/`: active, parked, and archived task evidence plus INDEX.
- Existing business/project docs: authoritative sources indexed by project knowledge.

Keep existing product, architecture, API, and design documents in their canonical owners. Create
AI-facing maps with source citations instead.

## Non-Git Fallback

In `single_lane` mode:

- Keep one current Change at a time.
- Disable worktree registration, completion-commit landing, contract conflict checks, and
  Integration commands.
- Keep knowledge, Change artifacts, validation, and five-Change evolution.
- `project migrate` may upgrade to `multi_lane` after Git exists; never run `git init` automatically.

## Initialization Failure

Initialization is transactional for creator-owned outputs. If a later link or route write fails,
remove only links that resolve to the newly created project Harness and route files created in that run, then
remove the incomplete project Harness. Preserve every pre-existing route, directory, and collision.

Existing project Harness migration first builds and validates a full candidate. Artifact `merge` means the
bundle supplies the complete merged candidate content, not an append operation. Execute bounded
Python/Node/PowerShell validation declarations against the candidate before a recoverable root
publication; a failure leaves current content, analysis, routes, and manifest unchanged.
