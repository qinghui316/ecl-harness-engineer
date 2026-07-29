# Environment Evidence Detection Guide

## Purpose

Provide bounded evidence collection strategies for `project-profile.json`. Use the contract in
`environment-config-guide.md` for output. This guide discovers facts; it does not create repository
Harness files or treat common defaults as project truth.

## Evidence Priority

1. Current CI and task-runner invocation.
2. Current manifests, workspaces, build files, deployment manifests, and typed config.
3. Current project development/runtime documentation consistent with code.
4. Source imports, routes, config reads, migrations, and tests.
5. Adapter candidates, kept as `candidate` until confirmed.

Conflicting evidence is an audit finding. Prefer current executable configuration over stale prose,
but record both sources and the unresolved decision when ownership is ambiguous.

## Bounded Scan

Start with top-level manifests and filenames. Select one or more adapters. Search for entrypoints,
configuration access, dependency clients, migration tools, health routes, and CI commands. Read
only relevant source slices. Exclude `.git`, dependency caches, vendor, generated output, build
output, coverage, logs, archives, and secret stores.

Never scan or copy real `.env`, credential files, keychains, cloud profiles, or deployment secrets.

## Project And Command Signals

### Go

- `go.mod`, `go.work`, `cmd/*/main.go`, `package main`.
- CI `go test`, `go vet`, staticcheck, golangci-lint, task runner targets.
- Database/message clients and configuration access are service candidates, not proof of active use.

### TypeScript/JavaScript

- `package.json` scripts, lockfile-selected package manager, workspaces, tsconfig references.
- Server/browser/CLI/library shape from entrypoints, exports, framework config, routes, and build.
- Preserve the exact package-manager invocation evidenced by the project.

### Python

- `pyproject.toml`, lockfiles, package entrypoints, framework app factories, CLI declarations.
- pytest/unittest/tox/nox/ruff/mypy commands from configuration or CI.
- A Python Harness host does not prove the target project uses Python.

### Java

- Maven/Gradle wrappers, modules, application plugins, main classes, test tasks, profiles.
- Prefer project wrappers and configured tasks over globally installed commands.

### Rust

- Cargo workspace/package metadata, binaries, examples, features, test/clippy/fmt commands.
- Workspace membership supplies package boundaries but not business-domain responsibility alone.

Use the selected adapters for detailed language conventions and generic fallback for unknown stacks.

## Service Signals

- Compose/Kubernetes/service manifests are high-confidence declarations for named environments.
- Migration configuration plus active repository usage is strong database evidence.
- Imports and client construction are medium-confidence and require an active call/config path.
- Tests may prove a service is optional or only required for integration mode.
- Documentation without current code/config support remains candidate.

Record purpose, modes, startup order, readiness, cleanup, and evidence. Do not assume Docker is
available merely because a Compose file exists.

## Variable Signals

Collect names from safe examples, typed config schemas, deployment manifests, and direct code reads.
For each name record required/optional, sensitive, modes, source, evidence, and unresolved default.

Sensitive patterns include password, secret, token, key, credential, signing, private, connection
URL, and provider-specific credentials. Pattern matching marks review; it does not authorize reading
the value.

## Readiness Discovery

- HTTP: verify a configured route and expected status from code/config/tests.
- TCP: verify a configured listener or service port.
- Log: verify a stable emitted message and avoid localized/dynamic text.
- Process: verify a stable identity and host command.
- None: explicitly record library/no-server behavior.

Timeout and retry values come from current tests/config or remain candidate. Readiness must test the
actual dependency needed by the intended command, not merely that a container or process exists.

## Baseline Execution

Run only existing configured commands appropriate to the task and available environment. Capture
command, cwd, exit code, duration, and bounded output/report path. Classify failure as introduced,
pre-existing, environmental, or blocked. Never weaken a gate or silently substitute a different
command to make the Harness appear healthy.

## User Decisions

Ask only for material unknowns such as runtime mode, external versus local service, required secret
provisioning method, or authoritative command when evidence conflicts. Ask no more than three
high-impact questions in one round. Accepted user statements become explicit evidence; silence does
not convert a guess into fact.

## Generated Projection Review

Before semantic completion verify:

- every configured fact cites project evidence;
- candidates remain labeled;
- no secret values or unsafe absolute paths appear;
- no unsupported service, port, endpoint, or command was invented;
- environment, commands, and verification pages agree;
- helper/check artifacts are explicitly accepted and validated;
- empty or library projects do not receive unnecessary runtime machinery.
