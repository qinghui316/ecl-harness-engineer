# Bootstrap Project

## Inputs

- Evidence-limited L1, critical rules, Registry preflight, and current Structured Change.
- User-confirmed purpose, language, application type, package identity, runtime constraints, and acceptance.
- `references/bootstrap/project.md`, the selected language/application variant, and project-specific
  environment constraints.

## Agent Judgment

Choose the smallest architecture that satisfies the confirmed first scenario. Separate domain and
application behavior from CLI/HTTP/framework boundaries. Do not infer a framework, service, port,
endpoint, persistence model, authentication scheme, package manager, or CI provider.

## Deterministic Commands

- Run `change new` for the bootstrap Structured Change, record its scope and paths, then run
  `change preflight` before plan approval and again before implementation.
- Validate the approved plan and Change artifacts before implementation.
- Run `python scripts/render_greenfield.py` for the one approved variant into an empty Worker output.
- Run the new project's declared build, test, lint, typecheck, start, and scenario checks.
- Run `change prepare-close`, commit business-project files, then bind the exact completion commit.

## Actions

1. Write WHAT/WHY, observable acceptance, non-goals, and confirmed product decisions in spec.
2. Write package layout, dependency direction, entrypoint, commands, environment, docs, tests, and CI in plan.
3. Obtain plan approval and map each AC to owner/path/validation tasks.
4. Implement source and project-owned files on the Worker branch.
5. Verify the primary scenario and all declared gates; update review and summary.
6. Close and integrate through the normal Lane/I2 workflow when applicable.

## Outputs

- Business source, tests, project commands, and evidence-supported documentation/CI.
- Complete Change evidence and exact completion commit in Git mode.
- Canonical project evidence suitable for a later project Harness refresh.

## Exit

The confirmed first scenario works, all accepted gates have outcomes, and the Change passes the
mature ECL close contract. No speculative service, secret, command, or architecture claim remains.

## Stop And Escalate

Stop on unresolved stack/application decisions, unavailable required runtime, security or public
contract ambiguity, failed plan review, or validation that contradicts completion.

## Rules

Apply HR-01 through HR-04, HR-14, HR-18, HR-23, and HR-24 plus
`references/rules/by-stage/bootstrap-project.md`.
