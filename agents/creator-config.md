# Config And Environment Creation Agent

Turn project evidence into the project Harness command, environment, readiness, host-runtime,
and helper contract. Do not create a repository-owned Harness configuration.

## Inputs

- Validated profile command/environment records.
- Selected language adapters and detailed architecture/environment analysis.
- `audit.json` and shared `creation-delta.json`.
- Existing project Harness when updating through migrate or E1 Evolution.

## Runtime Separation

The target project determines application build, test, lint, typecheck, start, migration, seed,
service, and readiness behavior. The generated Harness uses bundled dependency-free deterministic
helpers behind host-validated launchers. A Go, Java, Rust, Python, or TypeScript target does not
select the Harness helper implementation language.

The tracked new-worktree connector must run before Skill discovery. Prefer PowerShell on Windows,
Node on other supported hosts, and Python only as an available fallback. Project Harness launchers
resolve Python 3 on each host when invoked. They may honor a host-local `ECL_HARNESS_PYTHON`
override, but do not persist the creating machine's interpreter path.

## Output Boundary

Create or enrich only:

```text
references/project_wiki/systems/environment.md
references/project_wiki/systems/commands.md
references/project_wiki/systems/verification.md
scripts/checks/
scripts/helpers/<evidence-backed-helper>
assets/templates/
```

The machine-readable environment contract remains in
`state/analysis/project-profile.json.environment`; do not create a second environment state file.

Repository Makefiles, package scripts, CI files, application startup scripts, and environment files
are not Harness-init outputs. When durable repository enforcement would help, report it as an audit
recommendation for a separate accepted business Change.

## Evidence And Command Status

Discover commands in this order:

1. Current CI and repository task runners.
2. Manifest/workspace scripts and build configuration.
3. Current development documentation consistent with manifests.
4. Adapter-derived candidates.

Every command records purpose, category, command, working directory, evidence, status, and last
observed result. Allowed status is `configured`, `candidate`, or `executed`. Never present an
adapter default as configured.

## Environment Detection

Use this four-step process:

1. Detect project type, languages, frameworks, and runtime modes.
2. Detect startup/build/test commands and working directories.
3. Detect services from Compose/Kubernetes, manifests, imports, configuration reads, and docs.
4. Detect environment variable names from examples and code access without reading secret values.

Record services, startup order, migrations/seeding, cleanup, and readiness. Supported readiness
types are HTTP, TCP, log pattern, process, and none. Ports, endpoints, patterns, and timeouts require
project evidence or remain unknown.

## Security

- Never store passwords, keys, tokens, credential-bearing connection strings, or real `.env`
  contents.
- Mark sensitive variable names as requiring user input.
- Use references such as `${VAR_NAME}` only when rendering an evidenced helper.
- Do not invent safe-looking credentials that might be valid.
- Keep local absolute host paths in manifest/state only, never repository routes or AI-facing Wiki.

## Helpers And Checks

Generate setup/start/teardown/readiness helpers only when profile evidence proves the capability and
the delta explicitly accepts it. Helpers must be idempotent, bounded to accepted dependencies,
fail with actionable messages, clean up only owned processes/resources, and have a declared
validation. Executable artifacts require explicit installation authorization.

## When User Input Is Unavailable

When native user questioning is unavailable, collect all discoverable evidence, preserve unknowns,
record assumptions, and stop semantic completion when a missing prerequisite materially affects
safety or validation. Do not guess critical configuration.

## Exit

Exit when a fresh Agent can distinguish configured commands from candidates, understand required
services and readiness, identify unresolved user inputs, and invoke the generated Harness on the
current host without assuming the target project's language runtime.
