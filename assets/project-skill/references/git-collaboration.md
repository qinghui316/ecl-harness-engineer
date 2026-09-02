# Project Skill Git Collaboration

Read this reference only when the user asks to create, share, clone, update, review, or diagnose an
independent Git repository for this project Skill. The business project repository and this project
Skill repository are separate repositories. Do not initialize either repository as a side effect of
ordinary project work.

## Repository Boundaries

Share stable project knowledge and operating capability:

```text
SKILL.md
README.md
.gitignore
.github/
references/
scripts/
assets/
agents/
state/manifest.json
```

Keep local execution state on each collaborator's machine:

```text
state/changes/
state/registry/
state/evolution/
state/analysis/
state/migration/
locks, transactions, caches, logs, and Python runtime artifacts
```

Do not publish active, parked, or archived Change evidence. Promote a durable conclusion into its
current L1/L2/L3, rule, workflow, or Runtime module, validate it, and submit that stable change.

## Create A Git Version

Only proceed after the user explicitly asks for a Git version or remote publication.

1. Resolve the physical project Skill root. Refuse a symlink, Junction, secondary-worktree link, or
   a directory whose `state/manifest.json` does not match the project marker.
2. Create `.gitignore` before the first `git add`:

   ```gitignore
   /state/*
   !/state/manifest.json

   **/__pycache__/
   *.py[cod]
   *.log
   ```

3. Create a concise `README.md` that names the project id, matching business repository/commit,
   installation path, connector, local initialization, and validation commands.
4. Create `.github/pull_request_template.md` with the fields in **Pull Requests** below.
5. Run `git init` in the physical project Skill root, then require
   `git rev-parse --show-toplevel` to resolve to that exact directory.
6. Run project Doctor and knowledge check. Inspect `git ls-files state`; only
   `state/manifest.json` may be tracked.
7. Commit, add a remote, or push only when the user's request includes that action. Default a new
   remote to private visibility unless the user explicitly approves public project knowledge,
   references, checks, and assets.

If dynamic state was already tracked, remove it from the Git index without deleting local files,
then re-add only `state/manifest.json`. Never use a cleanup command to repair the index.

## Clone And Initialize

Use this order on a new machine:

```text
clone the matching business project
-> clone this project Skill to .agents/skills/<skill-name>
-> immediately run the project connector
-> run project doctor --repair-links
-> run knowledge scan/check
-> start local project work
```

Do not run an outer-repository `git add` between cloning the project Skill and running the
connector. The connector restores this machine's Git-common exclude and Codex/Claude links.
The business repository carries the managed PowerShell, Node.js, and Python connector variants so
each collaborator can use an available host without regenerating project routes.
`doctor --repair-links` creates only missing local state and does not rewrite the tracked manifest.
Use the host-native `.ps1`, `.cmd`, or `.sh` Harness launcher under `scripts/`; all three route to
the same Python Runtime and are distributed together.

If a matching project Skill already exists locally, do not clone over it. Verify the project id,
initialize Git in place if necessary, fetch the remote, and semantically reconcile stable content
while preserving ignored local state. Refuse a different project id.

Knowledge is directly usable only with the matching business-project revision. Related source
source changes require knowledge refresh or Change replanning; unrelated source changes are recorded without blocking
unaffected work.

## Pull Requests

Record:

```text
Project id
Base project Skill commit
Affected L1/L2/L3 module ids and paths
Matching business-project branch, commit, or PR
Contract impact
Knowledge check and project validation
```

Different L2 modules normally merge independently. Concurrent edits to the same L1/L2/L3 bridge,
rule, workflow, or Runtime module require an Agent to reconcile meaning against final source,
interfaces, contracts, and tests. Regenerate machine-owned indexes and rule views; do not resolve
them as independent prose.

Use the physical project Skill root for checkout, pull, merge, and commit. Same-machine business
worktrees share this one inner Git worktree. Do not overlap project Skill Git merge/pull with
migrate, application of an accepted E1 candidate, or another content transaction. If stable content
changes while a local Change is active, review the diff and rerun relevant preflight before
continuing.

## Safety Boundaries

- The business repository must not track the project Skill as files, an embedded repository, or a
  submodule.
- The project Skill repository must not track dynamic state beyond `state/manifest.json`.
- The business repository must share its managed project-id route and a usable connector so another
  Agent can discover the matching project Skill.
- Do not run `git clean -x`, double-force clean, or equivalent destructive cleanup from a business
  root that contains the physical project Skill.
- Git does not atomically version the two repositories. Pair them through project id, PR metadata,
  source fingerprints, and validation rather than assuming branch names imply compatibility.
