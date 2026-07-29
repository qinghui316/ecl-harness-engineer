# Locate

## Inputs

- Accepted scope and current Change.
- L1 overview, candidate L2 module/system maps, relevant L3 bridges, and reference maps linked by
  those project documents.
- Canonical source tree, configured search tools, and current contracts.

## Agent Judgment

Use knowledge to narrow the search, never to replace source confirmation. Semantic expansion is
allowed for locating code; implementation scope still requires source, contract, or user evidence.

## Deterministic Commands

- Run `change preflight` before source search.
- Use repository-native search, symbol, dependency, and test discovery commands.
- Run the Wiki stale checker when a selected L2/L3 page appears inconsistent with source.

## Actions

1. Disambiguate the request into plausible technical interpretations.
2. Select two or three candidate owners from L1/L2.
3. Search for declarations and callers without loading the whole repository.
4. Trace the relevant call/data path and confirm its tests, contracts, and error path.
5. Read L3 when terminology, schema, API, UI, provider, or runtime translation is required. Follow
   a reference source-map link already recorded in the selected L2/L3 before inspecting reference source.

## Outputs

- Owning module, impacted paths, relevant interfaces/contracts, call or data flow, and tests.
- Evidence citations and any knowledge drift signal.

## Exit

The modification point, owner, dependency direction, and verification surface are evidence-backed.

## Stop And Escalate

Stop when an L3 mapping lacks evidence, multiple owners remain materially plausible, or the current
contract conflicts with another Lane.

## Rules

Apply HR-01, HR-12, and HR-17 plus `references/rules/by-stage/locate.md`.
