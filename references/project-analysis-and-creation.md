# Real-Project Analysis And Harness Creation

## Purpose

Use this workflow to turn an empty, ordinary, or mature project into a project-bound local Harness.
Its `SKILL.md` is a progressive-disclosure entrypoint; the project Harness as a whole must match the project's evidenced
workflows, architecture, environment, rules, and coordination needs. The analysis that creates it
must remain deep, source-grounded, language-aware, and capable of handling an existing project
whose conventions were not designed for this Harness.

`scripts/harness_cli.py` provides deterministic scaffolding and state transitions. It is not a
replacement for architectural analysis, environment discovery, command verification, document
synthesis, or migration judgment.

## Stage Contract

Every stage has inputs, outputs, and an exit condition. Keep the analysis read-only until the
material delta is known.

| Stage | Inputs | Output | Exit condition |
| --- | --- | --- | --- |
| A. Locate and classify | User request, target path, nearest instructions, Git state | Project root, mode, intent, project Harness state, safety boundary | The target and `init`/`audit`/`migrate` mode are unambiguous |
| B. Discover evidence | Manifests, docs, source layout, CI, tests, env examples, worktrees | Source-backed project profile with confidence and evidence paths | Stack, commands, modules, environment, and unknowns are explicitly recorded |
| C. Analyze architecture | Profile, selected adapter, relevant source slices | Project identity, module/layer map, entrypoints, interfaces, flows, checks | Claims cite source evidence and speculative boundaries are excluded |
| D. Synthesize delta | Analysis, audit, existing project Harness inventory | Create/retain/merge/retire proposal | Every output has an owner and validation method |
| E. Create or migrate | Approved delta, templates, CLI | One local project Harness, runtime links, compact repo routes, optional accepted project checks | Files exist in the intended ownership boundary with no duplicate truth |
| F. Verify and hand off | Generated artifacts, original baseline, project gates | Structural, semantic, and project validation report | A new Agent can identify the project, next action, commands, and constraints from evidence |

## A. Locate And Classify

1. Resolve the requested path and read the nearest applicable `AGENTS.md` or runtime route before
   scanning broadly.
2. Detect Git top level, Git common dir, branch, HEAD, linked worktrees, dirty state, and whether
   the path is outside Git. Never run `git init` implicitly.
3. Classify the project separately along these axes:
   - source state: empty, scaffolded, ordinary existing, or mature;
   - project Harness state: absent, bootstrapped, current, outdated, or damaged;
   - coordination mode: `single_lane` or local `multi_lane`;
   - requested action: read-only audit, initialization, migration, or repair.
4. Inventory user modifications before mutation. A mature repository rehearsal is read-only unless
   the user separately authorizes migration.

For empty directories, read the initialization and project-detection sections in
`greenfield-templates.md`. Business-code templates are opt-in and must not be generated merely
because the project has no source yet.

## B. Discover Evidence

Use an evidence funnel so large repositories remain analyzable:

1. Read top-level names, manifests, lockfiles, existing project routes, and repository prose as
   candidate context rather than durable evidence.
2. Select candidate source roots and one or more adapters from concrete evidence.
3. Use repository search to locate entrypoints, imports, schemas, routes, configuration reads,
   tests, and CI commands. Search results narrow the next read; they are not architecture claims.
4. Read only relevant source slices to trace ownership, interfaces, critical flows, and dependency
   direction.
5. Confirm each durable claim against source code, a manifest/configuration file, a test, a
   configured command, an accepted contract, or an explicit user statement.

Do not preload full archive bodies, generated dependency trees, vendored code, build output, or
every source file. In a mature Harness, start with generated indexes, current route documents,
current architecture/API documents, active Change summaries, and only the history required to
explain a current rule.

### Analysis Bundle Contract

Before semantic `init`, a bundle-backed audit, or Evolution staging that needs broad project
analysis, create one temporary bundle:

```text
<bundle>/
├── project-profile.json
├── audit.json
├── creation-delta.json
├── architecture.json
└── artifacts/                       # only files named by creation-delta
```

The analyzer owns `project-profile.json` and `architecture.json`; environment guides and selected
adapters enrich profile commands/environment fields. The auditor owns `audit.json`. The creators jointly own
`creation-delta.json` and its artifact files. The CLI only validates and projects this bundle.

`scripts/build_analysis_bundle.py` is only a deterministic evidence extractor. It always emits a
`partial` or `bootstrap_only` draft with no audit score or authorized artifact. Analyzer, Auditor,
and Creators must review implementation evidence and write the final semantic bundle before using
`analysis_status: complete`.

Use this `project-profile.json` shape. Objects in evidence-backed arrays include an `evidence`
array of project-relative paths, canonical URLs, `user:` statements, or accepted
`contract:`/`registry:` references.

```json
{
  "schema_version": "1.0",
  "analysis_status": "complete",
  "project_name": "example",
  "purpose": {"summary": "What the project does", "confidence": "high", "evidence": ["src/app.ts", "tests/app.test.ts"]},
  "primary_flows": [{"name": "Main flow", "description": "...", "evidence": ["src/main.ts"]}],
  "languages": [{"name": "TypeScript", "confidence": "high", "evidence": ["package.json"]}],
  "frameworks": [],
  "package_managers": [],
  "source_roots": [{"path": "src", "confidence": "high", "evidence": ["package.json"]}],
  "entrypoints": [{"path": "src/main.ts", "kind": "service", "evidence": ["src/main.ts"]}],
  "modules": [{
    "id": "orders",
    "name": "Orders",
    "responsibility": "Own order lifecycle and public order contracts.",
    "kind": "business_domain",
    "roots": ["src/orders"],
    "entrypoints": ["src/orders/service.ts"],
    "interfaces": ["OrderService"],
    "dependencies": ["Persistence supplies OrderRepository"],
    "tests": ["tests/orders.test.ts"],
    "commands": ["npm test -- orders"],
    "boundaries": ["Other modules use OrderService"],
    "reference_sources": [],
    "evidence": ["src/orders/service.ts", "tests/orders.test.ts"]
  }],
  "commands": [{
    "purpose": "Run tests",
    "category": "test",
    "command": "npm test",
    "working_directory": ".",
    "status": "configured",
    "last_result": "not executed",
    "evidence": ["package.json"]
  }],
  "environment": {"services": [], "variables": [], "modes": [], "evidence": []},
  "ci": [],
  "bridges": [{
    "id": "terminology-to-code",
    "title": "Terminology To Code",
    "purpose": "Translate a proven domain term to its implementation owner.",
    "mappings": [{"from": "place order", "to": "src/orders/service.ts::place", "evidence": ["src/orders/service.ts", "tests/orders.test.ts"]}]
  }],
  "reference_projects": [],
  "global_boundaries": [
    {
      "rule": "All order state changes pass through OrderService.",
      "evidence": ["src/orders/service.ts"]
    }
  ],
  "unknowns": [],
  "evidence": ["package.json", "src/app.ts", "tests/app.test.ts"]
}
```

Each `global_boundaries` item uses a non-empty `rule` plus project evidence. Existing bundles that
use `name` with an optional `description` remain valid, but every complete record must contain
displayable boundary semantics; evidence alone is insufficient.

The same projection rule applies to primary flows, environment modes/helpers/object startup steps,
architecture components, dependency cycles, interfaces, and code paths: complete records must use
the semantic fields documented for their destination page, not evidence-only placeholder objects.

When the user requests a source reference, `reference_projects` contains a separately analyzed
project-local checkout at `.agents/reference-projects/<id>` or an existing
`reference-projects/<id>`. Record source, inspected commit, purpose, applicable problems, inspected
files, evidence-backed source modules, license evidence, unknowns, and reference-relative evidence.
Relevant target modules record the actual relationship in `reference_sources`; relevant L3 mappings
may cite reference evidence while retaining target evidence. Reference facts never populate target
modules, commands, environment, CI, or dependencies.

`audit.json` uses `schema_version: "1.0"`, `analysis_status`, evidence-backed strengths/gaps, and
the existing detailed audit dimensions where applicable. `creation-delta.json` uses:

```json
{
  "schema_version": "1.0",
  "mode": "init",
  "decisions": [{
    "source": "src/app.ts",
    "action": "retain",
    "owner": "project Harness knowledge",
    "projection": "L1 purpose citation",
    "validation": "source exists"
  }],
  "artifacts": [{
    "path": "references/workflows/runtime.md",
    "action": "create",
    "source": "artifacts/runtime.md",
    "owner": "creator-docs",
    "validation": "stage contract check",
    "evidence": ["src/runtime.ts"]
  }]
}
```

Artifact targets are restricted to project Harness `SKILL.md`, workflows, selected bootstrap
references, the rule source, `scripts/checks/`, evidence-backed `scripts/helpers/`, and templates.
Each artifact requires evidence, an owner, an allowed target path, validation, and explicit
authorization when executable. There is no capability-profile switch.
L1/L2/L3 are rendered only from the profile and architecture bundle. Unknown is a valid
result; invented certainty is not. A complete profile requires evidenced purpose, language,
implementation structure, and at least one flow/command/CI/boundary fact.
Without this complete bundle, `project init` is only a `bootstrap_only` installation and must not
be reported as semantic project initialization.

### Target Runtime Versus Harness Host Runtime

Keep these independent:

| Concern | Decision source |
| --- | --- |
| Target project's build, test, lint, start, package, and environment commands | Repository manifests, docs, CI, Make/task files, and the selected language adapter |
| Generated Harness command implementation | Bundled dependency-free Python CLI plus thin PowerShell, Windows `.cmd`, or POSIX launchers |

A Rust, Java, Go, or TypeScript target does not change the Harness host implementation to that
language. Conversely, the Python host is not evidence that a target project uses Python.

### Command Discovery

Use this evidence order:

1. Commands successfully invoked by current CI or repository task runners.
2. Named scripts or tasks in manifests, Makefiles, Justfiles, Taskfiles, Bazel files, Maven/Gradle,
   Cargo, Go modules, or Python project configuration.
3. Commands documented in current development instructions and consistent with manifests.
4. Adapter-derived candidates that remain marked `candidate` until verified.

For every command record `purpose`, `command`, `working_directory`, `evidence`, `status`, and the
last observed exit result when executed. Never report an adapter default as a configured project
command.

### Environment Discovery

Read `environment-detection-guide.md` and `environment-config-guide.md`. Inspect dependency
manifests, `.env.example` or equivalent, Docker Compose/Kubernetes files, migration tools,
configuration reads, and development docs. Record services, variables, readiness checks, startup
order, and unknown prerequisites. Never read secret values into generated knowledge and never copy
real `.env` contents.

## C. Analyze Architecture And Knowledge

Run the detailed procedure in `../agents/analyzer.md` and the selected adapter. At minimum:

1. Identify real source roots and generated/vendor exclusions.
2. Map modules from manifests, package/workspace boundaries, imports, entrypoints, tests, and
   current interfaces, imports, configuration, and tests. A directory name alone is insufficient evidence.
3. Trace dependency direction and report cycles without prematurely turning observations into
   permanent rules.
4. Extract key interfaces, implementations, API/schema/event/config ownership, critical request or
   job flows, and error-handling conventions.
5. Identify candidate mechanical checks and existing strict quality gates.
6. Separate current business truth from historical Harness narration.

Project knowledge is then synthesized using `knowledge-model.md`:

- L1 is the compact default map, sized by project complexity with no fixed byte or line limit; it
  retains complete project-level navigation while details live in L2/L3.
- L2 exists only for evidence-backed major modules and includes responsibilities, entrypoints,
  boundaries, tests, commands, citations, and a source fingerprint.
- L3 exists only for a proven semantic bridge such as product terminology to code, schema/API
  fields to owners, design tokens to implementation, or domain actions to handlers.
- `index.json` is generated. Do not create empty module or bridge documents.

## D. Audit And Delta Synthesis

Use `../agents/auditor.md` to assess more than file presence. Check:

- project identity and architecture fidelity;
- environment and command reproducibility;
- project-first routes and progressive context loading;
- ECL lifecycle and Change evidence;
- documentation source changes, duplication, and stale content;
- mechanical enforcement and actionable errors;
- local project Harness identity, runtime links, Registry health, Integration, and Evolution;
- migration responsibility and duplicate truth.

For migration, classify every existing artifact before edits:

| Decision | Meaning |
| --- | --- |
| `retain` | It remains authoritative in its current source |
| `move` | Current Harness behavior needs a different responsible document or module |
| `merge` | Multiple current sources must become one rule or knowledge entry |
| `retire` | Current guidance is contradicted or superseded, with evidence |
| `archive-only` | Useful history that must not load as current behavior |

For an existing project Harness, record the responsible module/document and validation for each
retained, merged, retired, or archive-only artifact before applying the migration.

## E. Create Or Migrate

1. Use `scripts/harness_cli.py` for project identity, transactional scaffold creation, one physical
   local project Harness, runtime links, Registry layout, and generated indexes.
2. Use the creator roles for semantic content:
   - `../agents/creator-docs.md` for repository routes, complete project knowledge, and project Harness
     knowledge maintenance;
   - `../agents/creator-config.md` for command/environment contracts and runtime helpers;
   - `../agents/creator-linters.md` for accepted deterministic checks with actionable errors.
3. Select concrete templates from `documentation-templates.md`, `linter-templates.md`, and the
   language adapter. Populate them from analysis; do not emit
   placeholder catalogs.
4. Keep detailed Harness rules, workflows, AI-facing knowledge, shared Registry, and Evolution
   state in the local project Harness.
5. Keep business code and optional human-facing documents in the repository. Add or update them
   only when the approved delta requires project documentation, commands, or checks; keep complete
   AI-facing knowledge in the project Harness.
6. Keep repository routes compact. Existing `AGENTS.md` or `CLAUDE.md` content is preserved and
   merged deliberately; it is never overwritten just to install a route.
7. Include the optional project Skill Git collaboration reference, but do not initialize an
   independent repository or create sharing metadata unless the user explicitly requests it.

## F. Semantic Verification

Structural validation is necessary but insufficient. Verify all of the following:

1. A fresh Agent can state what the project does, identify major workflows/modules, and choose the
   correct source entrypoint without loading the full repository.
2. Every generated command is configured or clearly marked as a candidate; executed commands have
   recorded results and pre-existing failures are separated from Harness regressions.
3. L1/L2/L3 entries cite existing evidence, contain no local paths in shareable repository files,
   and expose no secret values.
4. Empty projects contain no invented stack, module, service, or validation facts.
5. Existing projects retain their strict gates and user-owned docs.
6. Two worktrees share project identity and Registry while their checked-out files remain branch
   specific.
7. Mature migration does not load or copy full archives and does not compact old sources before
   capability ownership is proven.
8. `project doctor`, generated command self-tests, encoding scans, and applicable project gates
   pass or report actionable failures with an explicit scope.
9. A mature project produces sufficiently detailed, progressively loaded workflows and knowledge;
   passing a minimal scaffold check is not semantic success.

Run the scenarios in `validation.md`. Judge the result by whether ECL Harness Engineer creates a
useful project Harness from real evidence, not by generated line count.

## Handoff

Report the project profile, evidence-backed knowledge, command catalog, environment unknowns,
created and preserved files, runtime links, baseline results, migration decisions, and the exact
next Change command. For read-only work, report the proposed delta and stop before mutation.
