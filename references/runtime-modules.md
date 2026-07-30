# Deterministic Runtime Modules

This map is for maintaining the local Harness helpers or diagnosing a traceback. It is not part of
normal project work. Agents performing intake, planning, implementation, verification, Integration,
or Evolution should use the generated launchers and workflow documents without reading Python
internals.

## Ownership Boundary

Agents own semantic work: project purpose, module meaning, architecture interpretation, audit
judgment, knowledge writing, reference-source selection, and Evolution proposals. The runtime only
protects deterministic facts and transitions: ids, paths, indexes, links, Registry records, commit
identity, locks, review bindings, and recoverable publication.

The supported public entry remains `scripts/harness_cli.py`. Do not import an internal module from a
project workflow, add internal functions to the facade, or bypass a public command to mutate state.

## Module Map

| Module | Responsibility |
| --- | --- |
| `core.py` | Shared errors, constants, canonical ids, path safety, atomic I/O, process execution, and fingerprints |
| `contracts.py` | Machine validation for analysis, Change, architecture, audit, and secret-safe records |
| `reviews.py` | Structured Integration review and Evolution Judge report validation |
| `project.py` | Project identity, Git/common-dir/worktree discovery, canonical Skill paths, and manifest setup |
| `links.py` | Runtime copying, launchers, managed routes, connectors, junctions/symlinks, and worktree link repair |
| `analysis.py` | Four-file analysis-bundle schema, evidence, reference-source isolation, and artifact authorization |
| `rendering.py` | L1/L2/L3, architecture, rules, workflows, checks, and analysis publication |
| `registry.py` | Bound Registry record reads and Lane identity |
| `transactions.py` | Shared writer lock, short Registry lock, guarded commands, publication journal, rollback, and recovery |
| `changes.py` | ECL evidence, lifecycle, INDEX/search/context, preflight, contracts, and five-Change eligibility |
| `integration.py` | Exact commit-range Integration, independent review binding, I2 landing, and retry phases |
| `evolution.py` | E1 ownership, candidate staging, Judge gate, transactional publication, and results |
| `knowledge.py` | Read-only knowledge links, citations, fingerprints, drift, and entropy findings |
| `project_commands.py` | Project init/audit/migrate/doctor orchestration and single-Lane-to-Git upgrade |

`harness_cli.py` owns only argument parsing, command dispatch, JSON output, exit codes, and the
`__main__` entry. ECL Harness Engineer exposes `project init|migrate`; an installed project Harness
exposes only `project audit|doctor`.

## Command Ownership

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

Keep imports acyclic and pointed toward lower-level ownership:

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

This is an ownership direction, not a required loading order for Agents. Keep the package acyclic,
the facade limited to public parsing/dispatch, and module boundaries justified by ownership,
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
