# Workflow Contracts

## Stage Shape

Every generated workflow document declares:

1. Inputs.
2. Agent judgment.
3. Deterministic commands.
4. Outputs.
5. Exit criteria.
6. Stop and escalation conditions.

Use stage documents to route behavior. Keep the machine truth in
`references/rules/red_lines.yaml`; read generated `critical.md` globally and generated
`by-stage/<stage>.md` on demand. Refer to stable rule ids rather than restating them.

## Stages

| Stage | Required output | Exit criteria |
| --- | --- | --- |
| Intake | Scope, assumptions, acceptance, Change classification | High-impact ambiguity resolved or recorded as blocking |
| Locate | Candidate modules, call/data path, source evidence | Modification owner and verification surface identified |
| Plan | Accepted approach, contracts, tasks, validation | Plan review approved; no unresolved high-impact item |
| Implement | Scoped code and artifact updates | Tasks complete; no unauthorized scope expansion |
| Verify | Command outcomes and acceptance evidence | Required checks pass or failure is classified and reported |
| Close | Terminal evidence, validation, handoff, and Registry summary | Evidence complete; status is completed/blocked/abandoned |
| Integrate | Integration Record and landing candidate | Aggregate review ready for integration approval (I2) |
| Evolve | Proposal, independent score, result row | Passing delta applied or no modification recorded |

## Change Classification

Small work may skip a Change only when it is local, low risk, and has no API, schema, event,
permission, architecture, cross-module, release, or multi-step validation impact. Small work does
not count toward evolution.

Structured work creates one unique Change with:

- `summary.md`: current outcome, scope, status, verification, and handoff.
- `spec.md`: WHAT/WHY, acceptance, non-goals, constraints, assumptions, and open questions.
- `plan.md`: HOW, impacted owners, contract effects, risks, and verification plan.
- `tasks.md`: executable checklist mapped to acceptance criteria.
- `reviews/review.md`: plan, code, validation, contract, optional integration notes, and documentation review.

Keep complete Change files in project Harness `state/changes/` and record compact machine-readable
facts in the coordination Registry. Close is one-stage in Git and non-Git projects. A commit boundary is optional
Change metadata and becomes mandatory only when the user selects that Change for Integration.

## Plan Gate

Do not implement structured work until:

- Acceptance criteria are observable.
- High-impact contract effects are recorded in the coordination Registry.
- Planning identifies the owning module and relevant tests.
- The project-native plan review is approved.

Do not repeat questions already answered by an accepted user plan unless repository evidence
conflicts with it.

## Failure Feedback

Classify verification failures as introduced, pre-existing, environment, or blocked. Record
introduced failures in the Change. Repeated failures become evolution evidence; they do not become
rules immediately.
