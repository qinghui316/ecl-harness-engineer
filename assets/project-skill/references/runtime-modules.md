# Harness Runtime Diagnostics

Read this file only when maintaining a local Harness helper or diagnosing a traceback. Normal
project work uses the launchers and stage workflows.

## Responsibility Boundary

Agents decide project purpose, module meaning, architecture, audit findings, project knowledge,
reference relationships, and Evolution proposals. The runtime protects IDs, paths, indexes,
links, coordination Registry records, commit identity, locks, review bindings, and
crash-recoverable transactions.

An atomic write replaces one file or performs one filesystem rename. A complete Harness update is
a recoverable multi-file transaction with a journal, rollback, and crash recovery. A content digest
identifies exact Harness or candidate content; a source-state digest identifies the source snapshot
used for validation. `managed_by: agent` is the current knowledge model; the compatible `renderer`
value exists only for one-time migration of older project Harnesses.

The public entry is `scripts/harness_cli.py`. Project Harness installations expose
`project audit|doctor`; project creation and migration are performed by ECL Harness Engineer.
`doctor` diagnoses installation, runtime inventory, links, Registry identity, locks, and recovery.
`audit` adds Change evidence, rule views, project knowledge, citations, source-change findings, and
duplication findings.

## Modules

| Module | Responsibility |
| --- | --- |
| `core.py` | IDs, path safety, atomic I/O, process execution, content digests |
| `contracts.py` | Analysis, architecture, audit-rubric, Change, and secret-safe validation |
| `analysis.py` | Bundle evidence, reference-source isolation, artifact authorization |
| `project.py` | Project identity, Git/common-dir/worktree discovery, manifest facts |
| `links.py` | Launchers, managed routes, connectors, project-level links |
| `registry.py` | Bound coordination Registry record reads and parallel work Lane identity |
| `transactions.py` | Exclusive write/Registry locks, transaction journal, rollback, recovery |
| `knowledge.py` | Markdown metadata, generated catalog/source baseline, source fingerprints, source-change findings, and legacy index conversion |
| `rendering.py` | L1/L2/L3, architecture, rules, workflows, checks |
| `changes.py` | Change lifecycle, INDEX, preflight, contracts, Evolution eligibility |
| `reviews.py` | Integration review and independent Evolution review validation |
| `integration.py` | Exact ranges, integration approval (I2), Registry update, retry phases |
| `evolution.py` | Exclusive Evolution lease, staging, independent review, recoverable transaction, results |
| `project_commands.py` | Project audit/doctor and supported creation-time orchestration |

## Traceback Route

1. Reproduce through the public launcher and preserve JSON error output.
2. Start with the deepest `harness_runtime/<module>.py` frame.
3. Patch the module that owns the failed operation.
4. Run its failure/recovery test, the full runtime suite, and project Harness independence test.
