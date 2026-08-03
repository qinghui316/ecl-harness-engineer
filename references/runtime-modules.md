# Deterministic Runtime Modules

This map is for maintaining the local Harness helpers or diagnosing a traceback. It is not part of
normal project work. Agents performing intake, planning, implementation, verification, Integration,
or Evolution should use the generated launchers and workflow documents without reading Python
internals.

## Responsibility Boundary

Agents decide semantic work: project purpose, module meaning, architecture interpretation, audit
judgment, knowledge writing, reference-source selection, and Evolution proposals. The runtime
protects deterministic facts and transitions: IDs, paths, indexes, links, coordination Registry
records, commit identity, locks, review bindings, and crash-recoverable transactions.

The supported public entry remains `scripts/harness_cli.py`. Do not import an internal module from a
project workflow, add internal functions to the facade, or bypass a public command to mutate state.

## Canonical Runtime Terms

- **Project Harness:** the one physical project Skill directory shared by all local worktrees.
  **Skill root** means that directory's filesystem path; it is not a second object.
- **Atomic write:** one file replacement or one filesystem rename performed as a single operation.
- **Recoverable transaction:** a multi-file update with a journal, rollback, and crash recovery; the
  complete Harness update is not described as one atomic write.
- **Content digest:** SHA-256 over sorted project-relative paths and raw bytes for physical files
  under `SKILL.md`, `references/`, `scripts/`, `assets/`, and `agents/`; exclude `state/`,
  `__pycache__/`, and `.pyc` files. Candidate validation rejects unsafe links separately.
- **Source-state digest:** SHA-256 over the sorted evidence-source path, status, and source
  fingerprint tuples used by one command. A tracked source fingerprint uses its Git blob; other
  UTF-8 text normalizes line endings before hashing relative path plus content.
- **Exclusive write lock:** prevents Integration finalization and Evolution from changing stable
  Harness content at the same time.
- **Exclusive Evolution lease:** records which process is performing periodic Harness review (E1)
  and the fixed set of Change IDs under review.
- **Filesystem operation lock:** an OS-level command lock that keeps readers and writers outside a
  project Harness root replacement.
- **Short coordination Registry lock:** serializes one bounded Registry update. The
  `evolution-state` lock is this lock applied to pending/evaluated/result state.
- **Generated document / agent-maintained document:** prose descriptions of the compatible
  `managed_by: renderer|agent` values.
- **E1 approval:** user approval to start one periodic Harness review; `E1` is not the review result.
- **Integration approval (I2):** user approval after aggregate validation and independent review of
  the exact Integration candidate commit.

Public commands acquire the filesystem operation lock before any short coordination Registry lock.
The exclusive write lock and Evolution lease are longer-lived records used across commands; do not
invert this order or acquire a command-level lock from inside a short Registry lock.
Only Runtime commands and read-only Runtime checks participate in the filesystem operation lock.
Direct Agent reads of Markdown do not. Agents must not inspect the Harness filesystem while a
migration or accepted Evolution update is replacing the root; use the public status or doctor
command after the operation completes.

## Module Map

| Module | Responsibility |
| --- | --- |
| `core.py` | Shared errors, constants, canonical ids, path safety, atomic I/O, process execution, and fingerprints |
| `contracts.py` | Machine validation for analysis, Change, architecture, audit, and secret-safe records |
| `reviews.py` | Structured Integration review and independent Evolution review validation |
| `project.py` | Project identity, Git/common-dir/worktree discovery, physical project Harness paths, and manifest setup |
| `links.py` | Runtime copying, launchers, managed routes, connectors, junctions/symlinks, and worktree link repair |
| `analysis.py` | Four control-file analysis-bundle schema, evidence, reference-source isolation, and artifact authorization |
| `rendering.py` | L1/L2/L3, architecture, rules, workflows, checks, and migration-bundle application |
| `registry.py` | Bound coordination Registry record reads and parallel work Lane identity |
| `transactions.py` | Exclusive write lock, short Registry lock, guarded commands, transaction journal, rollback, and recovery |
| `changes.py` | ECL evidence, lifecycle, INDEX/search/context, preflight, contracts, and five-Change eligibility |
| `integration.py` | Exact commit-range Integration, independent review binding, integration approval (I2), and retry phases |
| `evolution.py` | Exclusive Evolution lease, candidate staging, independent review, recoverable transaction, and results |
| `knowledge.py` | Markdown metadata, generated catalog/source baseline, source fingerprints, source-change findings, and legacy index conversion |
| `project_commands.py` | Project init/audit/migrate/doctor orchestration and single-Lane-to-Git upgrade |

`harness_cli.py` owns only argument parsing, command dispatch, JSON output, exit codes, and the
`__main__` entry. ECL Harness Engineer exposes `project init|migrate`; an installed project Harness
exposes only `project audit|doctor`.

## Command Responsibility

| Public command | Primary module | Supporting modules to inspect next |
| --- | --- | --- |
| `project init|migrate` | `project_commands.py` | `analysis.py`, `rendering.py`, `links.py`, `transactions.py` |
| `project audit` | `project_commands.py` | `knowledge.py`, `changes.py`, `links.py`, `transactions.py` |
| `project doctor` | `project_commands.py` | `links.py`, `registry.py`, `transactions.py` |
| `change *` | `changes.py` | `contracts.py`, `registry.py`, `transactions.py` |
| `integrate *` | `integration.py` | `reviews.py`, `changes.py`, `registry.py`, `transactions.py` |
| `evolve *` | `evolution.py` | `analysis.py`, `rendering.py`, `reviews.py`, `transactions.py` |
| `knowledge scan|check` | `knowledge.py` | `project.py`, `transactions.py` |

## Dependency Direction

Keep imports acyclic and pointed toward lower-level responsibilities:

```text
core
-> project / contracts / registry
-> links / analysis / transactions / reviews
-> knowledge / rendering
-> changes
-> integration / evolution
-> project_commands
-> harness_cli
```

This is a responsibility direction, not a required loading order for Agents. Keep the package
acyclic, the facade limited to public parsing/dispatch, and module boundaries justified by responsibility,
test isolation, and diagnostics rather than line-count targets.

## Traceback Triage

1. Reproduce through the public launcher and preserve its JSON error and exit code.
2. Start with the deepest `harness_runtime/<module>.py` frame, then use the command table above.
3. Patch the module where a symbol is looked up. For failure injection, patch
   `integration.git`, `integration.atomic_write_json`, `evolution.release_writer`, or
   `transactions.transaction_move`, rather than facade attributes.
4. Run the focused failure/recovery test, then the full CLI suite and project Harness independence
   scenario.
5. Keep behavior changes out of a mechanical module move. New command or state semantics require a
   separate approved Change.
