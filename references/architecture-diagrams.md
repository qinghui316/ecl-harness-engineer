# Evidence-Backed Architecture Projections

Use this reference during Analyzer and creator-docs work when project evidence contains relationships
that are easier to navigate as diagrams. The project Harness receives only project-specific
Mermaid, never this template catalog.

## Machine Owner

`architecture.json` owns diagram facts. Supported records are:

- `layers`: level, packages, description, evidence.
- `dependencies`: from, to, relation, optional module_id, evidence.
- `components`: id, label, responsibility, optional module_id, evidence.
- `key_interfaces`: name, location, implementations, optional module_id, evidence.
- `code_paths`: name, flow, optional module_id, optional `semantic_bridge: true`, evidence.
- `circular_dependencies` and `error_patterns`.

Every node and edge requires existing source, manifest, test, canonical-document, accepted-contract,
or user-confirmed evidence. Imports establish dependencies; declarations and usage establish
interface implementations; entrypoints/calls/tests establish code paths. Directory names and search
similarity only locate evidence and cannot become edges.

## Progressive Projection

| Projection | Content | Loading trigger |
| --- | --- | --- |
| L1 overview | Compact project-level diagrams that improve routing; include each distinct global flow needed for orientation | Default project orientation |
| L2 `systems/architecture.md` | layers, package/module dependencies, components, boundaries, interface map | Architecture or cross-module work |
| L2 `modules/<id>.md` | relationships whose `module_id` matches that module | Work scoped to the module |
| L3 `bridges/critical-flow-*.md` | complex evidenced sequence with `semantic_bridge: true` | API/schema/event/config/runtime translation boundary |

Large graphs split by module or flow. Do not place full dependency graphs in L1.

## Diagram Forms

Render only forms supported by facts:

1. Package/module dependency graph from `dependencies`.
2. Component relationship graph from `components` plus evidenced relations.
3. Interface-to-implementation map from `key_interfaces[].implementations`.
4. Critical sequence from ordered `code_paths[].flow`.
5. Module boundary view from layer/module ownership plus dependencies.
6. Call hierarchy or data flow only when ordered call/data edges are recorded.

Each generated page lists citations and stores source fingerprints in project Wiki `index.json`.
`knowledge scan/check` reports changed or missing sources. A changed fingerprint is a review/replan
signal; it never authorizes automatic deletion or invention of replacement edges.

## Exit

Exit when every rendered node/edge is traceable, unsupported relations are absent, diagrams are
progressively loaded from L2/L3, and a source change produces a drift finding.
