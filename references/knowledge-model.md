# Layered Project Knowledge

## Principle

Keep current AI-facing knowledge self-contained, source-backed, and progressively read. Repository
prose may help analysis locate claims, but it is not a durable knowledge dependency. The project
Harness stores enough verified knowledge for the next agent to act without reopening those files.

## Layers

### L1 Overview

`references/project_wiki/overview.md` is the default project map. Scale it to project complexity;
there is no fixed byte or line limit. Include:

- Project purpose and primary user/system workflow.
- Major modules with one-sentence responsibilities.
- Commands, environment, verification entrypoints, and major system maps.
- Current architectural boundaries that affect most Changes.
- Links to L2 modules, not their full contents.

Do not include phase history, archive ledgers, full directory trees, or current Lane status. If the
map becomes hard to scan, move descriptive detail to L2/L3 while retaining the project-level links
needed to discover every major owner. Length alone is not a knowledge finding.

### L2 Systems And Designs

Use L2 for evidence-backed modules, systems, domains, target architecture, and important design
documents. Include the applicable responsibility, Owner, boundaries, dependencies, evidence, and
links to narrower L3 details. A target architecture is durable knowledge but must remain `target`
until implementation evidence supports reclassification as `current`.

Renderer-owned module maps include:

- Stable module id and root directories.
- Responsibility and owner boundary.
- Important entrypoints, interfaces, data owners, and verification commands.
- Cross-module dependencies that affect planning.
- Source evidence paths and last scanned content identity.

Create L2 only when source structure, interfaces, tests, or accepted contracts prove the module. Do not generate
placeholder modules from directory names alone.

### L3 Precise Contracts And Bridges

Use L3 for interfaces, schema, events, call flows, terminology mappings, and implementation
standards. Create a bridge only when the project contains a real translation boundary, for example:

- Product terminology to code names.
- API/schema/event/config fields to owning modules.
- Design tokens or UI component names to implementation APIs.
- Domain actions to commands, handlers, routes, or tests.

Search expansion may use inferred synonyms to locate code. Decisions and durable bridges require
source citations, accepted contracts, or user statements.

## Generated Index

`references/project_wiki/index.json` is generated and contains document id, layer, source paths,
source fingerprints, and update time. Never hand-edit it.

`references/project_wiki/catalog.md` is also generated. It groups every indexed document by
semantic layer, kind, status, Owner, and module. The default route is overview -> catalog -> the
smallest relevant L2/L3 set; filenames and directories do not define layer.

Agent-owned Markdown uses this frontmatter:

```yaml
---
ecl:
  id: office-v2-target
  layer: L2
  kind: target
  status: accepted
  owner: office-architecture
  modules: [agent-office]
  evidence:
    - user:accepted target architecture
    - registry:change/office-v2
  managed_by: agent
---
```

Layers are `L1|L2|L3`; kinds are `current|target|decision|guide`; statuses are
`proposed|accepted|in_progress|implemented|retired`. Full refresh replaces only renderer-owned
current facts. Matching Agent ownership of both an existing id and path is an explicit takeover;
an id-only or path-only collision fails closed.

Use relative project paths in knowledge documents and indexes. Resolve local absolute paths only in
the running process; never persist them in manifest, Registry, INDEX, or knowledge state.

## Refresh Rules

- Worker Changes publish provisional path and contract facts to the Registry, not stable knowledge.
- Integration lands accepted code and optional business documents and records baseline, Registry, and evolution signals;
  it does not rewrite L1/L2/L3.
- Initialization and full migration may install a complete evidence-backed analysis bundle.
- A focused migrate may publish an explicitly requested formal Agent-owned document immediately.
- After five qualified Changes and E1, focused Evolution may update, merge, retire, or promote any
  Agent-owned L1/L2/L3 document. Full Evolution refreshes renderer-owned current facts only when
  whole-project analysis is actually required.
- `harness-knowledge scan` and `check` are read-only. They report missing sources, fingerprint
  drift, broken links, duplicate ownership, misplaced detail, and uncited L3 claims; they never apply a
  semantic refresh.
- Run them when source drift is suspected, preflight identifies related drift, or audit, migration,
  or E1 needs a mechanical knowledge report. Ordinary explanation, navigation, and source reading
  follow the document links without running a knowledge command.
- L1/L2/L3 is a periodic AI index and can lag up to four integrated Changes. Structured preflight
  reads baseline events and fingerprints only the knowledge sources selected by current paths,
  contract paths, and owner module. When those sources drift, return `refresh-needed/replan` rather
  than silently trusting stale Wiki text. Full source scans belong to knowledge check, audit,
  migration, or E1.
- Resolve current facts in this order: Registry contracts/baseline events, shared current Change
  evidence, repository code/manifests/configuration/tests/interfaces, then L1/L2/L3. An unrelated baseline advancement
  does not force a Lane to stop.

## Progressive Reading

Load L1 first. Select L2 by affected paths, modules, or contracts. Select L3 only for a matching
translation boundary. Do not preload every module, bridge, Change, or archive.

Reference relationships are part of the project knowledge graph. A relevant L2/L3 page links its
reference source map, and the map points to inspected source. Direct reference research starts from
`reference_projects/index.md`.

## Entropy Decisions

Classify stale material as:

- `retain`: still changes current agent behavior.
- `merge`: overlaps another current entry and should become one shorter statement.
- `retire`: contradicted or superseded current guidance.
- `archive-only`: useful history that should not stay in current knowledge.
