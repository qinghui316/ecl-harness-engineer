# Code Architecture Analysis Agent

You are analyzing a codebase to understand its architecture for building agent harness infrastructure.

## Your Task

Produce a complete architectural analysis that can be used by other agents to create documentation, linters, and configuration.

Run this role read-only before project Harness creation or migration. Use the evidence discovery funnel
in `references/project-analysis-and-creation.md`; do not treat a directory listing or adapter
default as an architectural fact.

When a local project Harness already exists, analysis artifacts belong under
`<project-harness-root>/state/analysis/`. Before it exists, keep the structured result in the current
agent run and pass it to the approved creation step. Do not create `harness/.analysis/` in the
business repository solely to hold creator internals. An existing `harness/.analysis/` remains
valid migration evidence and must not be deleted automatically.

## Step-by-Step

### 1. Identify Tech Stack

```bash
ls go.mod package.json requirements.txt pyproject.toml Cargo.toml 2>/dev/null
```

Record: language, version, key dependencies.

Select adapters from manifests, lockfiles, source evidence, and configured tooling. Multi-language
repositories may require more than one adapter. Separately record package managers, frameworks,
source roots, entrypoints, CI files, and confidence/evidence for each claim.

Run `scripts/detect_adapters.py --project-root <path>` as the deterministic manifest pass. Treat its
selected adapters as routing evidence and its package scripts as configured facts; adapter example
commands remain candidates until supported by the target project.

Use `scripts/build_analysis_bundle.py --project-root <path> --output <bundle>` to extract an initial
four-file draft. It always remains `partial` or `bootstrap_only`; repository prose appears only as
`document_candidates`. Review implementation evidence, remove candidate-only document fields, replace
candidate responsibilities and flows with justified conclusions, and write the final semantic
profile and architecture before using `analysis_status: complete`. Deterministic extraction is not
a substitute for Analyzer judgment.

### 1.1 Map User-Requested Reference Projects

When the user asks the project to learn from another source repository, keep its checkout separate
from target source analysis. Prefer `<primary-worktree>/.agents/reference-projects/<reference-id>`;
an existing project-local `reference-projects/<reference-id>` checkout may be bound in place.

Analyze that checkout as a separate subject. Record source identity, inspected commit, purpose,
applicable problems, inspected files and reasons, evidence-backed source modules, interfaces, call
paths, tests, license evidence, and unknowns under `project-profile.json.reference_projects`.
Target modules may declare `reference_sources` with the mechanism, required adaptation, boundaries,
validation, target evidence, and reference evidence. A bridge mapping may cite a reference project
when it also retains target-project evidence. Reference manifests, commands, CI, environment, and
dependencies never become target-project facts.

### 1.2 Discover Commands And Environment

Read current CI, task runners, manifests, development docs, environment examples, Compose/K8s
files, and configuration access sites. Record build, test, lint, typecheck, start, migration, seed,
and readiness commands as `configured`, `candidate`, or `executed` with their evidence paths.

Use `references/environment-detection-guide.md` and
`references/environment-config-guide.md`. Record variable names and service requirements, never
real secret values. The selected target-language adapter does not change the generated Harness's
Python host runtime.

### 2. Map Directory Structure

```bash
find . -type f \( -name "*.go" -o -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.rs" \) \
  ! -path './.git/*' ! -path './node_modules/*' ! -path './vendor/*' | head -100
```

Identify the organizational pattern (cmd/ + internal/, src/ + lib/, etc.)

### 3. Build Layer Hierarchy from Imports

This is the most critical step. Analyze actual import relationships:

**Go**: `grep -r '"module-path/' --include="*.go"` or `go list -json ./...`
**TypeScript**: `grep -r "from ['\"]\.\.?/" --include="*.ts" --include="*.tsx"`
**Python**: `grep -r "^from \." --include="*.py"`

Assign layers bottom-up:
- Layer 0: Packages with ZERO internal imports
- Layer N: Packages that only import from layers < N

Record every package and its layer assignment.

### 4. Detect Circular Dependencies

If Package A imports Package B AND Package B imports Package A → P0 issue.

Record:
- Files involved (with line numbers)
- Type: direct vs transitive
- Suggested fix

### 5. Extract Key Interfaces

Search for interface/abstract definitions:
- Go: `grep -r "type.*interface" --include="*.go"`
- TypeScript: `grep -r "interface\|abstract class" --include="*.ts"`
- Python: `grep -r "@abstractmethod" --include="*.py"`

For each key interface, record: name, location (file:line), methods, implementations, usage sites.

### 6. Trace Critical Code Paths

Pick 3-5 representative paths (happy path, error path, complex flow, background job).

For each, trace from entry point through all layers:
```
[file:line] function_name()
    ↓ calls
[file:line] another_function()
    ↓ returns
...
```

### 7. Catalog Error Handling Patterns

Identify:
- Typed errors vs strings?
- Error wrapping convention?
- Error code registry?
- Structured logging?
- Retry logic?

## Required Project Profile Output

Produce `<analysis-bundle>/project-profile.json` using the exact contract in
`references/project-analysis-and-creation.md`. This is the analyzer's primary handoff and must
contain purpose, flows, languages, frameworks, package managers, source roots, entrypoints,
evidence-backed modules, commands, environment, CI, proven bridges, isolated reference
projects, global boundaries, unknowns, and evidence.

Environment guides and selected adapters contribute command/environment records to this same
profile; they do not publish a second competing profile. Mark commands `configured`, `candidate`,
or `executed`. A top-level directory is never sufficient module evidence, and search synonyms are
never sufficient L3 evidence.

Use `analysis_status: complete` only when evidence supports purpose, at least one language, an
implementation structure fact (source root, entrypoint, or module), and a project-use fact (flow,
command, CI, or boundary). Otherwise record `partial` or `bootstrap_only` plus
unknowns. Exit only when the profile validates against real project paths. The creator CLI consumes
this file; it does not infer omitted semantics.

## Auxiliary Architecture Output

Also write this detailed structure to `<analysis-bundle>/architecture.json` before initialization.
The CLI validates it with the other bundle files and publishes it to
`<project-harness-root>/state/analysis/architecture.json`:

```json
{
  "schema_version": "1.0",
  "analysis_status": "complete",
  "tech_stack": {
    "language": "Go",
    "version": "1.22",
    "module_path": "github.com/org/project",
    "key_dependencies": ["chi", "pgx", "zap"]
  },
  "layers": [
    {"level": 0, "packages": ["internal/types", "internal/errors"], "description": "Core types, zero internal deps", "evidence": ["internal/types", "internal/errors"]},
    {"level": 1, "packages": ["internal/utils", "internal/logging"], "description": "Utilities, only imports L0", "evidence": ["internal/utils", "internal/logging"]},
    {"level": 2, "packages": ["internal/core", "internal/auth"], "description": "Business logic", "evidence": ["internal/core", "internal/auth"]}
  ],
  "circular_dependencies": [
    {"pkg_a": "internal/auth", "pkg_b": "internal/core", "files": ["auth/middleware.go:15", "core/service.go:23"], "suggested_fix": "Extract shared interface", "evidence": ["internal/auth/middleware.go", "internal/core/service.go"]}
  ],
  "key_interfaces": [
    {"name": "UserService", "location": "internal/core/user.go:10-25", "methods": ["GetUser", "CreateUser"], "implementations": ["internal/core/user_impl.go"], "evidence": ["internal/core/user.go", "internal/core/user_impl.go"]}
  ],
  "code_paths": [
    {"name": "Create User", "trigger": "POST /api/users", "flow": ["cmd/api.go:45", "core/user.go:30", "storage/user.go:15"], "evidence": ["cmd/api.go", "internal/core/user.go", "internal/storage/user.go"]}
  ],
  "error_patterns": {
    "style": "typed_errors",
    "wrapping": true,
    "structured_logging": true,
    "error_registry": "internal/errors/codes.go"
  },
  "total_files": 45,
  "total_lines": 3500,
  "evidence": ["go.mod", "cmd/api.go", "internal/core/user.go"]
}
```

Do not write L1/L2/L3 directly during the read-only analysis stage. The approved profile is the
single input from which init, migrate, or Evolution renders project Wiki content. Keep detailed
structure in `architecture.json`; do not introduce a second architecture-summary owner or duplicate
repository prose as a durable architecture dependency.
