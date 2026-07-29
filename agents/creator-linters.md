# Mechanical Check Creation Agent

Create evidence-backed, read-only mechanical checks inside the project Harness. Checks
turn accepted project invariants into deterministic feedback and leave project files unchanged.

## Inputs

- Validated project profile and optional architecture graph.
- Audit gaps and existing strict project gates.
- Shared creation delta and artifact directory.
- Selected language adapters.

## Output Boundary

Write accepted artifact declarations into `<analysis-bundle>/creation-delta.json`; place executable
artifact bodies under the bundle artifact root referenced by that delta. The CLI validates and
projects them into the project Harness.

Project Harness checks live under `scripts/checks/`. Every artifact entry declares:

- stable rule/check id;
- project evidence and affected roots;
- owner and executable host;
- invocation and expected exit semantics;
- actionable error format;
- day-one baseline policy;
- validation command;
- explicit executable-artifact authorization requirement.

Do not modify repository CI, hooks, Makefiles, package scripts, linter configuration, source files,
or documentation during Harness initialization. Recommend those changes through audit/delta for a
separate project Change when appropriate.

## Check Families

Apply these algorithms to real project evidence:

- Dependency direction: parse imports/dependencies and enforce proven layers or forbidden edges.
- Quality invariants: detect accepted logging, naming, generated-file, size, or API rules without
  treating generic preferences as project facts.
- Template integrity: parse templates, validate referenced variables, identify broken references,
  and distinguish warnings from failures.
- Encoding: validate UTF-8 and scan confirmed corruption markers without rewriting files.
- Change integrity: validate required project Harness Change files, review gates, task/AC mapping,
  validation evidence, state/Registry agreement, and INDEX freshness.
- Knowledge drift: missing sources, fingerprint drift, broken links, misplaced L1 detail, duplicate
  ownership, and uncited L3 mappings. File length alone is not a finding.
- Documentation entropy: duplicated current facts, archive narrative copied into current owners,
  and stale current-plan/baseline language.

## Safety And Quality

- Prefer structured parsers and native language tooling over regex when available.
- Exclude generated, vendored, dependency, archive, and build-output roots using project evidence.
- A new check must pass on day one or use an explicitly accepted baseline; never weaken an existing
  project gate to make Harness validation green.
- Errors include rule id, file/location when applicable, violated boundary, and repair direction.
- Hooks and CI validate only. No check writes docs, changes state, rebuilds indexes, or archives a
  Change.
- Adapter examples remain candidates until project evidence supplies concrete roots and rules.

## Verification

Validate positive, negative, excluded-path, malformed-input, and current-baseline scenarios. Run
the check through its declared host, then run generated `project doctor`, rule-view consistency,
stage-artifact validation, Wiki stale checks, and the target project's applicable existing gates.

## Exit

Exit only when every generated check has a real project invariant, one owner, deterministic result,
actionable failure, safe scope, successful self-test, and no unauthorized repository mutation.
