# Project Harness Environment And Command Contract

## Purpose

Define one evidence-backed environment model for the analyzer, creators, generated L2 systems, and
project checks. The profile is machine input; Wiki systems are the Agent-facing projection.

## Ownership

```text
project manifests/CI/docs/code
  -> analyzer + adapters
  -> project-profile.json environment/commands
  -> project_wiki/systems/environment.md
  -> project_wiki/systems/commands.md
  -> project_wiki/systems/verification.md
```

Detailed local analysis is stored in `state/analysis/project-profile.json.environment`. Secret values never
enter profile, Wiki, scripts, Registry, or logs.

## Profile Shape

```json
{
  "commands": [
    {
      "purpose": "Run unit tests",
      "category": "test",
      "command": "npm test",
      "working_directory": ".",
      "status": "configured",
      "last_result": "not executed",
      "evidence": ["package.json"]
    }
  ],
  "environment": {
    "project_type": "service",
    "modes": [
      {"name": "development", "description": "Local API development", "evidence": ["README.md"]}
    ],
    "services": [
      {
        "name": "database",
        "type": "postgresql",
        "required_for": ["start", "integration-test"],
        "startup_order": 10,
        "source": "docker-compose.yml",
        "readiness": {"type": "tcp", "host": "localhost", "port": 5432, "timeout_seconds": 30},
        "evidence": ["docker-compose.yml"]
      }
    ],
    "variables": [
      {
        "name": "DATABASE_URL",
        "required": true,
        "sensitive": true,
        "modes": ["development", "test"],
        "source": "src/config.ts",
        "evidence": ["src/config.ts"]
      }
    ],
    "startup_order": ["database", "migration", "application"],
    "unknowns": [],
    "evidence": ["docker-compose.yml", "src/config.ts"]
  }
}
```

Omit unsupported objects rather than emitting placeholders. Empty projects use empty arrays and
explicit unknowns.

## Command Evidence

Discover in order:

1. Commands invoked by current CI or repository task runners.
2. Named scripts/tasks in manifests, workspaces, Make/Just/Task files, Bazel, Maven/Gradle, Cargo,
   Go modules, or Python configuration.
3. Current development documentation consistent with configured tooling.
4. Adapter-derived candidates.

Status meanings:

- `configured`: directly declared by current project evidence.
- `candidate`: plausible adapter result that still requires confirmation or execution.
- `executed`: run in the stated working directory with result recorded.

Never upgrade a candidate to configured because it is conventional. Record command, purpose,
category, working directory, evidence, last exit status, observed timestamp, and baseline failure
classification when executed.

## Four-Step Detection

### 1. Project Type And Runtime

Classify service, CLI, frontend, library, worker/job, mobile, monorepo, or mixed from manifests,
entrypoints, deployment files, routes, exports, and documentation. Multi-language projects may use
multiple adapters. Keep target runtime separate from Harness host runtime.

### 2. Startup And Verification

Find build, test, lint, typecheck, start, integration-test, migration, seed, and teardown commands.
Capture working directory and mode. A command documented without matching current tooling remains
candidate until verified.

### 3. Services And Ordering

Use Compose/Kubernetes, dependency manifests, imports, config reads, migrations, and docs. Record
what each service is required for, startup order, ownership, and cleanup. Do not infer a database
solely from a generic library in unused code.

### 4. Variables And User Inputs

Read variable names from `.env.example`, `.env.sample`, deployment manifests, typed configuration,
and code access sites. Never read real `.env` values. Mark sensitive names and required modes.

Ask only when a missing answer changes startup, validation, safety, or ownership. Otherwise record
an assumption or unknown. In autonomous mode, never fill a critical unknown with a common default.

## Readiness

Supported types:

| Type | Evidence | Required fields |
| --- | --- | --- |
| HTTP | Configured health/readiness route | endpoint, port, expected status, timeout |
| TCP | Configured listening service | host, port, timeout |
| Log pattern | Stable documented startup message | pattern, timeout |
| Process | Stable process command/identity | check command, timeout |
| None | Library or no long-running process | reason |

Do not invent `/health`, port 8080, or a log phrase. Readiness helpers must time out, fail
actionably, and clean up only processes/resources they own.

## Sensitive Configuration

- Store variable names and references such as `${VAR_NAME}`, never values.
- Never store passwords, tokens, API keys, private internal URLs, or connection strings containing
  credentials.
- Do not emit safe-looking test secrets that might be valid elsewhere.
- Mark required sensitive names for user input and keep them out of generated examples/logs.
- Local machine paths belong only in local manifest/state.

## Helper Generation

Setup/start/teardown/migrate/seed/readiness helpers are optional project Harness artifacts. Generate
one only when profile evidence proves the capability, creation delta accepts it, placeholders are
fully replaced, executable installation is authorized, and validation passes. Helpers are
idempotent, dependency-bounded, fail-fast, and ownership-aware.

Do not modify repository Makefiles, package scripts, CI, Compose, Kubernetes, or application config
as a side effect of project Harness initialization. Recommend such changes through an explicit
business-project Change.

## Exit

The contract is complete when a new Agent can choose the correct project command and mode,
understand required services/readiness/user inputs, distinguish configured from candidate facts,
and reproduce observed validation without receiving a secret.
