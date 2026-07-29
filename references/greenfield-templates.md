# Greenfield Project Bootstrap

Use this reference when a project has little or no application evidence and the user wants to
create its first application. Project Harness initialization records honest unknowns; business
source is created through an approved Structured Change.

## Route

```text
Detect an evidence-limited project
-> install a bootstrap-only project Harness
-> confirm purpose, language, application type, constraints, and acceptance
-> create one Structured Change
-> approve spec, plan, tasks, and validation
-> render one selected variant into an empty Worker output
-> adapt source, tests, commands, documentation, and CI to the accepted plan
-> verify and close with an exact completion commit
-> Integration + I2 in Git multi-Lane mode
```

Use the renderer only after plan approval:

```text
python <ecl-harness-engineer>/scripts/render_greenfield.py \
  --variant <go|typescript|python>-<cli|web> \
  --output-root <empty-worker-output> \
  --project-name <name> [--module <go-module>]
```

The output root must be empty. The renderer owns executable starter source; this reference owns
selection, architecture, output expectations, adaptation boundaries, and validation.

## Required Decisions

Confirm only decisions that materially affect the scaffold:

1. Product purpose, target user, and first observable scenario.
2. Language: Go, TypeScript/Node, or Python, unless another adapter is evidenced.
3. Application type: CLI or Web API.
4. Package/module name and supported runtime version.
5. Public contract, external services, security/persistence constraints, and CI provider when
   applicable.

Existing answers are reused. Low-risk unknowns become assumptions. Language, application type,
external service, authentication, persistence, security, and public-contract uncertainty stop at
the clarification gate.

## Bootstrap Change Contract

The Structured Change records:

- WHAT/WHY in `spec.md`: purpose, user, primary scenario, observable acceptance, non-goals.
- HOW in `plan.md`: stack, package layout, dependency direction, entrypoint, tests, commands,
  environment, documentation, and CI.
- Tasks mapping each acceptance criterion to owner, path, and validation.
- Review of architecture, security, commands, tests, environment, and project files.
- A clean completion commit containing only accepted business-project artifacts.

The project Harness owns Change evidence. Application source, project documentation, manifests,
task scripts, and CI belong to the project repository.

## Shared Architecture

Start with this dependency direction and collapse layers when the application is small:

```text
entrypoints/adapters -> application/core -> domain/types
infrastructure implementations -> application-owned interfaces
```

- Domain values have no framework dependency.
- Application code owns use cases and interfaces required from infrastructure.
- CLI/HTTP entrypoints translate input and output around application calls.
- Infrastructure implements application-owned interfaces.
- Tests exercise domain/application behavior without the full runtime where practical.
- Errors cross boundaries as stable domain errors or typed error objects.

A directory is created only when it has an accepted responsibility.

## Variant Contracts

### Go CLI

Expected owners:

```text
go.mod
cmd/<project>/main.go
internal/app/
internal/adapters/              # only for an external boundary
README.md
```

Validate `go test ./...`, `go build ./...`, and `go vet ./...`. Process wiring and exit codes stay
in `main`; behavior stays in `internal/app`.

### Go Web API

Add `cmd/api` and `internal/httpapi` around the same application boundary. Routes, address,
readiness, persistence, and authentication come from the accepted Change. Handler tests exercise
the accepted route without requiring a live server when possible.

### TypeScript CLI

Expected owners:

```text
package.json
tsconfig.json
src/app.ts
src/cli.ts
test/
README.md
```

Use the accepted package manager and strict TypeScript configuration. Project scripts cover the
configured build, test, typecheck/lint, and start operations.

### TypeScript Web API

Keep application behavior independent of transport and add the accepted HTTP adapter/server.
Framework packages and request/response schemas enter only when the plan requires them. Test the
HTTP contract and one framework boundary when a framework is selected.

### Python CLI

Expected owners:

```text
pyproject.toml
src/<package>/application.py
src/<package>/cli.py
tests/
README.md
```

Use a `src/` layout and the project-selected test, lint, and typecheck tools. Candidate tools become
configured only after the Change adds and validates them.

### Python Web API

Keep application behavior framework-independent and add the accepted HTTP adapter. Framework,
ASGI/WSGI command, address, readiness route, and dependency versions come from the plan. Add a live
readiness test only when the runtime contract requires a process.

## Renderer Output

`scripts/render_greenfield.py` owns the concrete starter files for all six variants. Each render
produces:

- a language manifest and package/module identity;
- application behavior separated from CLI or HTTP transport;
- unit tests and, for Web API variants, an HTTP contract test;
- a README command matrix;
- a CI placeholder that must be adapted to the accepted provider and pinned runtime.

The Worker reviews every rendered file against the Change. Placeholder behavior such as the
starter `accepted` scenario is replaced only when the accepted spec requires it. The renderer does
not choose product behavior, external services, public routes, secrets, or deployment policy.

## Documentation

Create only project-owned documents justified by project complexity:

| Document | Content |
| --- | --- |
| `README.md` | Purpose, first scenario, setup, real commands, current limitations |
| Architecture | Dependency direction, modules, entrypoint, first flow, accepted decisions |
| Development | Prerequisites, package manager, commands, variable names |
| Testing | Test levels, commands, fixtures/services, failure attribution |
| Security | Trust boundaries, secret-variable names, validation, dependency policy |
| Product | Target user, priorities, non-goals, vocabulary supplied by the user |

Project knowledge cites these documents and code without copying their full content.

## Environment And Readiness

For each accepted service record purpose, owner, startup order, command or prerequisite, readiness
type and target, migration/seed behavior, teardown ownership, and unresolved prerequisites. Record
variable names and sensitivity, never values. Helpers are idempotent, time-bounded, and clean only
resources they created.

## Project Commands And CI

Make/task targets and package scripts invoke validated project commands. CI installs the accepted
runtime and runs the same build/test/lint/typecheck gates. A failing baseline is reported rather
than weakened. Wiring a project Harness check into repository CI is a separate accepted business
Change.

## Bootstrap Profile

Before business source exists, the profile is `bootstrap_only` with empty modules, commands,
services, bridges, and evidence-backed facts. Unknowns name the unconfirmed purpose, stack,
application type, and first acceptance. After the bootstrap Change lands, migrate or a later E1
Evolution can build a complete profile from canonical evidence.

## Verification

Before close:

1. Declared build, test, lint, and typecheck commands pass or have honest failure attribution.
2. The primary CLI/API acceptance is exercised at the appropriate level.
3. Dependency direction matches the approved plan.
4. No secret value, guessed address, credential, service, or public contract was introduced.
5. Project documentation names only commands and behavior that exist.
6. Spec, plan approval, AC/task mapping, review, and summary pass the ECL gate.
7. Git-backed work records the exact clean completion commit before Integration.

## Failure Handling

| Failure | Response |
| --- | --- |
| Purpose or application type unknown | Stop before business scaffold planning |
| Selected language lacks a proven adapter | Add a project-specific adapter in the Change |
| Tool/runtime unavailable | Record an environmental failure without switching stacks |
| Framework choice changes public architecture | Return to plan review |
| Rendered command fails | Attribute and repair before close |
| CI differs from local gates | Align commands or document the deliberate platform difference |
