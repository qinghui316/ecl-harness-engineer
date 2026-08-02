# Project Harness Mechanical Checks

Use this reference when project evidence supports a deterministic invariant. Creator roles define
the accepted check and its evidence; `scripts/checks/` owns the executable implementation.

## Check Contract

Each check declares:

- stable rule/check id and owner;
- project evidence and affected roots;
- input format and parser/tooling choice;
- exclusions for generated, vendor, dependency, build, and archive roots;
- invocation, exit codes, and actionable failure format;
- day-one baseline policy;
- positive, negative, malformed-input, and excluded-path validation.

A failure names the rule, location, violated boundary, evidence owner, and repair direction. Checks
are read-only and never rewrite source, documentation, Change state, indexes, hooks, or CI.

## Dependency Direction

Use when manifests, imports, interfaces, tests, or architecture evidence proves layers or
forbidden edges.

1. Select the language-native parser or dependency graph when available.
2. Normalize package/module identities to the evidenced owner map.
3. Compare actual directed edges with allowed layer directions and explicit exceptions.
4. Report source, imported owner, violated rule, and expected dependency direction.
5. Treat unresolved/dynamic imports as warnings unless the project defines a mechanical policy.

Do not infer a layer from a top-level directory name. Cycles are errors only when the accepted
architecture forbids them.

## Quality Invariants

Use for evidenced project rules such as logging APIs, naming, generated-file ownership, source-size
limits, error wrapping, public API placement, or forbidden framework dependencies.

- Prefer AST/type/language tooling over text matching.
- Keep generic style preferences out of project facts.
- Point to the existing canonical rule or accepted contract.
- Separate new violations from an explicitly accepted baseline.
- Preserve strict existing project gates.

## Template Integrity

Parse the real template format and validate:

- declared variables and references;
- required files/includes;
- duplicate or unknown keys;
- path ownership and traversal boundaries;
- syntax and renderability with a bounded fixture.

Missing required variables, broken includes, invalid syntax, and path escape are errors. Unused
optional variables or style inconsistencies are warnings unless the project makes them strict.

## Encoding

Validate UTF-8 decoding for source and project-owned text. Scan known corruption markers only as a
candidate finding, then confirm the damaged literal before repair. Exclude binary and generated
content through evidence-backed patterns. A check reports corruption; it never bulk re-encodes.

## Change And Index Integrity

Validate:

- required `summary/spec/plan/tasks/reviews/review` evidence;
- resolved clarification and approved plan;
- AC-to-task/owner/path/validation mapping;
- completed tasks, review coverage, validation result, and optional Integration notes;
- Change directory, Registry status, record identity, and INDEX agreement;
- active/parking/archive state and generated INDEX freshness.

Identity mismatch, missing evidence, stale/tampered INDEX, and Registry divergence are errors.

## Project Knowledge Integrity

Validate:

- L1 required sections, project-level navigation coverage, and valid L2 links;
- L2/L3 citations and source fingerprints;
- reference-source map checkout identity and citations;
- broken internal links, invalid metadata, orphan documents, and missing indexed files;
- interface/API/schema/document drift;

Missing sources, bad links, index corruption, unsafe paths, and exact ID/path conflicts are
mechanical errors. Misplaced detail, stale wording, duplicate semantics, current/target meaning,
Owner quality, and archive density belong to Agent/Judge review; Runtime does not infer them from
keywords. Knowledge scan/check reports only; init, migrate, or accepted E1 publication applies
stable updates.

## Stack Adaptation

### Go

Use `go list`, `go/packages`, `go/ast`, or existing project tooling when configured. Preserve module
and internal-package semantics. A regex import scanner is only a bounded fallback for simple
fixtures and must report its limitation.

### TypeScript And JavaScript

Use TypeScript compiler/module-resolution APIs, ESLint rules, workspace manifests, or existing
dependency tools when available. Resolve aliases and project references before evaluating edges.

### Python

Use `ast`, importlib metadata, package manifests, and configured tools. Distinguish relative imports,
namespace packages, optional imports, and dynamic loading. Never treat an incomplete regex sample
as a production checker.

### Java And Rust

Use Maven/Gradle or Cargo metadata plus language parsers/tooling. Apply workspace/module boundaries
from manifests rather than directory names.

## Publication

An executable check is installed only through an evidence-backed creation-delta artifact with an
allowed path, owner, explicit authorization, and passing validation declaration. Register its
invocation in project Harness verification knowledge. Repository CI integration, when desired, is
a separate project Change.

## Exit

Exit when the invariant is real, the parser is proportionate, exclusions are evidenced, failures
are actionable, day-one validation passes or has an accepted baseline, and the check cannot mutate
project or Harness state.
