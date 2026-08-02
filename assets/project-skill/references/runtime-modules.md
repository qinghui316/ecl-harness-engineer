# Harness Runtime Diagnostics

Read this file only when maintaining a local Harness helper or diagnosing a traceback. Normal
project work uses the launchers and stage workflows.

## Ownership

Agents decide project purpose, module meaning, architecture, audit findings, project knowledge,
reference relationships, and Evolution proposals. The runtime protects ids, paths, indexes,
links, Registry records, commit identity, locks, review bindings, and recoverable publication.

The public entry is `scripts/harness_cli.py`. Project Harness installations expose
`project audit|doctor`; project creation and migration are performed by ECL Harness Engineer.
`doctor` diagnoses installation, runtime inventory, links, Registry identity, locks, and recovery.
`audit` adds Change evidence, rule views, project knowledge, citations, drift, and entropy.

## Modules

| Module | Responsibility |
| --- | --- |
| `core.py` | IDs, path safety, atomic I/O, process execution, fingerprints |
| `contracts.py` | Analysis, architecture, audit-rubric, Change, and secret-safe validation |
| `analysis.py` | Bundle evidence, reference-source isolation, artifact authorization |
| `project.py` | Project identity, Git/common-dir/worktree discovery, manifest facts |
| `links.py` | Launchers, managed routes, connectors, project-level links |
| `registry.py` | Bound Registry record reads and Lane identity |
| `transactions.py` | Writer/Registry locks, publication journal, rollback, recovery |
| `knowledge.py` | Read-only metadata, links, source fingerprints, drift, and index/catalog integrity |
| `rendering.py` | L1/L2/L3, architecture, rules, workflows, checks |
| `changes.py` | Change lifecycle, INDEX, preflight, contracts, Evolution eligibility |
| `reviews.py` | Integration review and Evolution Judge validation |
| `integration.py` | Exact ranges, I2 landing, Registry update, retry phases |
| `evolution.py` | E1 ownership, staging, protected gate, Judge, publication, results |
| `project_commands.py` | Project audit/doctor and supported creation-time orchestration |

## Traceback Route

1. Reproduce through the public launcher and preserve JSON error output.
2. Start with the deepest `harness_runtime/<module>.py` frame.
3. Patch the module that owns the failed operation.
4. Run its failure/recovery test, the full runtime suite, and project Harness independence test.
