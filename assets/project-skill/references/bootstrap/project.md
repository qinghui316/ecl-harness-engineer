# Bootstrap Project Reference

Use this reference while the project profile is `bootstrap_only` and the user wants to create the
first business application. Initialization creates the project Harness; business source is created
only through one approved Structured Change.

## Decisions Required Before Projection

1. Product purpose, target user, and first observable scenario.
2. Language and supported runtime version.
3. CLI or Web API application type.
4. Package/module identity and dependency constraints.
5. Public commands or endpoints, external services, security boundaries, and CI provider when applicable.

Record confirmed decisions as `user:` evidence. Language, application type, persistence,
authentication, service, security, and public-contract uncertainty blocks implementation.

## Change Contract

- `spec.md` owns WHAT/WHY, observable acceptance, and non-goals.
- `plan.md` owns selected layout, dependency direction, entrypoint, commands, environment, tests,
  documentation, and CI; it requires approval before implementation.
- `tasks.md` maps every acceptance criterion to owner/path and validation.
- `review.md` covers architecture, code, security, commands, environment, contract, optional
  Integration notes, knowledge, and documentation entropy.
- Optional Integration notes record whether a later exact commit boundary will be needed.

Prefer this dependency direction unless the approved plan proves a better project boundary:

```text
entrypoints/adapters -> application/core -> domain/types
infrastructure implementations -> application-owned interfaces
```

Small projects may combine directories while keeping application behavior independently testable.

## Selected Variant

This generic bootstrap reference intentionally contains no language source templates. After the
user confirms one language/application variant and the plan is approved, run the project Harness
deterministic renderer for exactly that variant:

```text
python scripts/render_greenfield.py --variant <go|typescript|python>-<cli|web> \
  --output-root <empty-worker-output> --project-name <name> [--module <go-module>]
```

The renderer provides real source, tests, commands, documentation, and a CI starting point. Review
all output against the accepted spec and environment contract. Those files are Worker Change
outputs, not project Harness initialization output.

## Environment And Close

For each accepted service record startup order, readiness, migration/seed behavior, teardown owner,
variable names, sensitivity, and unknowns. Helpers are idempotent, time-bounded, validated, and
clean up only resources they created.

Before close, run the declared primary scenario and gates, verify dependency direction, reject
secret values and guessed runtime facts, and complete all ECL evidence. When the user requests
Integration, establish an exact commit boundary and continue through I2.
