# Layered Project Knowledge

## Principle

Keep current AI-facing knowledge compact, source-backed, and progressively loaded. Raw repository
documents and Change history remain evidence. The project Harness stores the current projection that
helps the next agent act.

## Layers

### L1 Overview

`references/project_wiki/overview.md` is the default project map. Scale it to project complexity;
there is no fixed byte or line limit. Include:

- Project purpose and primary user/system workflow.
- Major modules with one-sentence responsibilities.
- Canonical source documents and verification entrypoints.
- Current architectural boundaries that affect most Changes.
- Links to L2 modules, not their full contents.

Do not include phase history, archive ledgers, full directory trees, or current Lane status. If the
map becomes hard to scan, move descriptive detail to L2/L3 while retaining the project-level links
needed to discover every major owner. Length alone is not a knowledge finding.

### L2 Modules

Create one document per evidence-backed module. Include:

- Stable module id and root directories.
- Responsibility and owner boundary.
- Important entrypoints, interfaces, data owners, and verification commands.
- Cross-module dependencies that affect planning.
- Source evidence paths and last scanned content identity.

Create L2 only when source structure or existing documentation proves the module. Do not generate
placeholder modules from directory names alone.

### L3 Semantic Bridges

Create a bridge only when the project contains a real translation boundary, for example:

- Product terminology to code names.
- API/schema/event/config fields to owning modules.
- Design tokens or UI component names to implementation APIs.
- Domain actions to commands, handlers, routes, or tests.

Search expansion may use inferred synonyms to locate code. Decisions and durable bridges require
source citations, accepted contracts, or user statements.

## Generated Index

`references/project_wiki/index.json` is generated and contains document id, layer, source paths,
source fingerprints, and update time. Never hand-edit it.

Use relative project paths in knowledge documents. Local absolute paths belong only in manifest or
Registry state.

## Refresh Rules

- Worker Changes publish provisional path and contract facts to the Registry, not stable knowledge.
- Integration lands canonical code/documents and records baseline, Registry, and evolution signals;
  it does not rewrite L1/L2/L3.
- Initialization and migration may install a complete evidence-backed analysis bundle.
- After five qualified Changes and E1, Evolution rescans canonical evidence and may update, merge,
  retire, or promote L1/L2/L3 together with the rest of the project Harness.
- `harness-knowledge scan` and `check` are read-only. They report missing sources, fingerprint
  drift, broken links, duplicate ownership, misplaced detail, and uncited L3 claims; they never apply a
  semantic refresh.
- Run them when source drift is suspected, preflight identifies related drift, or audit, migration,
  or E1 needs a mechanical knowledge report. Ordinary explanation, navigation, and source reading
  follow the document links without running a knowledge command.
- L1/L2/L3 is a periodic AI index and can lag up to four integrated Changes. Every stage preflight
  reads baseline events and related source drift. When the current Change touches an affected path,
  module, or contract, return `refresh-needed/replan` rather than silently trusting stale Wiki text.
- Resolve current facts in this order: Registry contracts/baseline events, shared current Change
  evidence, canonical repository code/documents, then L1/L2/L3. An unrelated baseline advancement
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
