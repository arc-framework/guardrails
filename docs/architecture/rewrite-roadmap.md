# Scratch: Rewrite Roadmap

> Purpose: This is not a full spec. It is a working roadmap and reminder for the rewrite.
> Primary references:
>
> - `docs/superpowers/specs/2026-05-01-universal-guardrail-revisit.md`
> - `docs/superpowers/specs/2026-04-20-packages-restructure-design.md`

---

## 0. North star

The rewrite should optimize for one clear differentiator:

**Intent-preserving guardrailing**

The system should not only sanitize and block. It should estimate whether, after sanitization and safe rehydration, the final answer still matches the user's original intent.

This gives the project three measurable dimensions:

- privacy preservation,
- adversarial resistance,
- semantic fidelity.

If a feature does not clearly strengthen one of those three dimensions, it is probably not a priority for the rewrite.

---

## 1. First things

These are the first tasks to start. Do not jump to advanced detectors or dashboards before these are stable.

### 1.1 Lock the rewrite boundary

- Keep the rewrite centered on enterprise prompt/response guardrailing for external LLM use.
- Treat multi-transport universal guardrails as architecture roadmap, not first implementation target.
- Keep the initial usage shape narrow: sanitize input, send to external LLM, verify and rehydrate output.

### 1.2 Fix package boundaries before feature growth

- Establish `packages/common`, `packages/core`, and `packages/api`.
- Keep `common` tiny and dependency-light.
- Put all actual guardrail logic in `core`.
- Keep `api` as a thin deployment surface.
- Do not let existing `arc-common` become the new guardrail `common` by accident.

### 1.3 Preserve the current code as migration source

- Treat `python/arc-guardrails/src/arc_guard/` as the source to split, not code to delete.
- Move and refactor in phases rather than rewrite every file from zero.
- Reuse tests as behavioral guardrails while structure changes.

### 1.4 Define the baseline pipeline early

The baseline pipeline should be fixed first:

1. Sanitize
2. Defend
3. Generate
4. Verify and Rehydrate

Every new feature should fit one of those four stages.

### 1.5 Build the evaluation harness early

- Create a benchmark corpus before advanced model features.
- Include normal enterprise prompts, privacy-sensitive prompts, jailbreaks, deception attempts, and rehydration edge cases.
- Keep this harness alive from the start so every new feature can be measured.

This is important because the dissertation argument depends on comparative evidence, not just implementation breadth.

### 1.6 Set engineering standards from day zero

- Treat this as an enterprise-grade reusable Python library, not an experimental script bundle.
- Standardize on Python 3.11+ features and conventions from the start.
- Keep `ruff`, `pytest`, and `mypy` as non-negotiable quality gates for every package.
- Prefer small focused classes, typed constructors, clear ownership, and explicit public APIs.
- Use `Protocol` interfaces to preserve contracts when implementations move or split across packages.
- Use proper models for every important domain concept instead of loose dictionaries crossing layers.

### 1.7 Validate data at every boundary

- Validate configuration on load.
- Validate request and response models at API boundaries.
- Validate findings, policy decisions, and guard results at pipeline boundaries.
- Validate adapter input and output before external calls.
- Avoid passing unchecked data across layers.

The goal is not to add ceremony to every helper function. The goal is to make every important junction typed, validated, and safe to refactor.

### 1.8 Logging, OTEL, exceptions, and concurrency are first-class

- OTEL starts on day one, including hello-world flows.
- Every important stage in the pipeline should be observable: sanitize, defend, generate, verify, rehydrate, report.
- Use structured logging with request and trace correlation, not freeform print-style logs.
- Define structured exception handling rules, including which failures are fail-open and which are fail-closed.
- Keep blocking model inference off the event loop.
- Use async for I/O, thread pools for blocking CPU or model calls when needed, and document thread-safety requirements for shared registries or caches.

### 1.9 Reuse before build

- Before implementing a subsystem, check whether a strong open-source library already solves the problem well.
- Record a short adopt-vs-build note before introducing custom infrastructure.
- Prefer proven libraries for validation, observability, retries, and protocol integration unless the thesis contribution requires custom behavior.

This rule is especially important for:

- data validation,
- OTEL instrumentation,
- structured logging,
- retry and resilience patterns,
- model wrappers and embedding helpers.

### 1.10 Use project tools deliberately

- Use SpecKit to keep spec, plan, and task work aligned.
- Use Claude superpowers and repo-local docs as planning accelerators, not as substitutes for architecture decisions.
- Use CodeGraph or equivalent code intelligence tools when mapping dependencies before moving modules.
- Refresh project context when plans materially change.

### 1.11 Documentation is part of the rewrite

- Keep architecture notes and roadmap docs current as structure changes.
- Maintain one-page walkthrough summaries per spec in `docs/walkthrough/`.
- Treat documentation as a required deliverable, not cleanup work for the end.

---

## 2. Must-have features

These are required for the rewrite to be coherent, useful, and defensible.

### 2.1 Structured entity sanitization

- Detect sensitive enterprise entities.
- Replace them with typed placeholders, not generic placeholders only.
- Support examples such as:
  - `[EMPLOYEE_NAME]`
  - `[CUSTOMER_NAME]`
  - `[INTERNAL_PROJECT]`
  - `[CONFIDENTIAL_LOCATION]`

Why this is must-have:

- It is the foundation of privacy preservation.
- It improves meaning retention compared with naive masking.

### 2.2 Composable policy routing

- Support multiple findings and multiple actions in one run.
- Allow different strategies for different findings.
- Preserve the design direction from the restructure draft: route findings to strategies instead of forcing one global action.

Why this is must-have:

- The current single-strategy design is too weak for realistic enterprise use.
- This is core architecture, not polish.

### 2.3 Risk-adaptive behavior

- Low risk: sanitize and continue.
- Medium risk: sanitize and warn.
- High risk: partial refusal or restricted answer.
- Critical risk: block and explain.

Why this is must-have:

- Binary allow/block is too crude.
- A policy story is more useful and more defensible than a toy filter.

### 2.4 Graceful refusal envelope

- Every blocked or restricted action should return a structured refusal.
- Include what triggered the action, what policy fired, and what the user should do next.
- Keep the refusal both machine-readable and human-readable.

Why this is must-have:

- This is important for usability, auditing, and API design.

### 2.5 Explainable guardrail decisions

- Record what was detected.
- Record what was masked.
- Record why the system blocked, warned, or modified output.
- Record whether fidelity verification passed or failed.

Why this is must-have:

- Enterprise systems need auditability.
- Academic reviewers need to see that the system is explainable.

### 2.6 Clarification path instead of only hard refusal

- When risk is uncertain or fidelity is too low, ask for safe reformulation.
- Avoid dead-end blocks when a clarification question can recover the task.

Why this is must-have:

- It makes the system more intelligent and practical.
- It gives a better answer to "how should guardrails behave in real use?"

### 2.7 Observability and evaluation hooks

- Structured logs.
- Traceable decision flow.
- Metrics for masking, blocking, latency, and fidelity outcomes.

Why this is must-have:

- Without this, you cannot defend the system empirically.

---

## 3. Research contribution features

These are the features that create the "magic factor" and make the work feel like more than integration.

### 3.1 Semantic intent lock

This is the core differentiator.

The system should bind together:

- the original user intent,
- the sanitized prompt,
- the rehydrated answer,

and detect when the final answer drifts too far from what the user actually meant.

This is the best candidate for the thesis contribution.

### 3.2 Intent fidelity score

- Compute an intent representation before sanitization.
- Compute a second representation after rehydration.
- Measure whether the final answer still responds to the original query.
- Trigger warning, clarification, or refusal if fidelity drops below threshold.

Why this matters:

- It directly answers the professor's concern about rehydration correctness.
- It transforms the project into a measurable research problem.

### 3.3 Rehydration safety checker

- Do not blindly reinsert masked entities into the final answer.
- Check whether the surrounding answer structure is still safe and semantically aligned.
- Rehydrate only if both risk and fidelity conditions pass.

Why this matters:

- It makes rehydration an active verification stage rather than string replacement.

### 3.4 Stateful jailbreak and deception detection

- Go beyond single-turn prompt checks.
- Track attack patterns across turns:
  - gradual policy erosion,
  - role-play coercion,
  - "just for testing" framing,
  - indirect prompt injection hidden in earlier context.

Why this matters:

- This is more interesting than basic regex jailbreak detection.
- It is much closer to enterprise conversational reality.

### 3.5 Adversarial evaluation harness

- Build comparative evaluation, not just feature demos.
- Compare:
  1. raw LLM call,
  2. sanitize-only,
  3. sanitize plus jailbreak defense,
  4. sanitize plus jailbreak defense plus fidelity verification.
- Include prompt sets for:
  - benign enterprise requests,
  - privacy-sensitive requests,
  - single-turn jailbreaks,
  - multi-turn deception,
  - rehydration failures.

Why this matters:

- This is critical for dissertation quality.
- It demonstrates improvement rather than claiming it.

### 3.6 Fidelity-oriented metrics

At minimum, track:

- sensitive entity masking precision and recall,
- jailbreak detection precision and recall,
- semantic similarity between original intent and rehydrated output,
- intelligibility or task-completion score,
- latency overhead.

Why this matters:

- These are the numbers that make the contribution credible.

---

## 4. Nice-to-have features

These are useful, but they should not delay the core rewrite.

### 4.1 More transports

- REST payload adapters.
- Event-stream adapters.
- gRPC adapters.
- File and document pipelines.

These support the universal guardrail vision, but they are future expansion, not first implementation priorities.

### 4.2 More provider integrations

- Additional reporter adapters.
- Additional feature-flag sources.
- More external service hooks.

Useful for productization, but not central to the thesis contribution.

### 4.3 Rich policy authoring UX

- Large YAML rule sets.
- Admin-oriented policy editors.
- Runtime dashboards.

Helpful later, but not the source of originality right now.

### 4.4 Product dashboard and analytics UI

- Dashboard for incidents, fidelity drift, and policy actions.

Good enterprise surface area, but not a first rewrite target.

### 4.5 Advanced packaging polish

- Full multi-package publishing.
- Extensive extras and distribution polish.
- Broader install matrices.

Good open-source polish, but after the engine and research core are stable.

---

## 5. What not to start yet

Do not start these before the core rewrite path is stable.

- Too many transport adapters.
- Too many provider integrations.
- Cosmetic dashboards.
- Large policy DSL expansion without evaluation.
- Basic regex-only feature expansion presented as novelty.
- Product packaging polish before the fidelity pipeline is proven.

If time is limited, cut these first.

---

## 6. Practical build order

This is the recommended order of work.

### Stage A: Rewrite foundation

- establish package boundaries,
- move current code into new homes,
- preserve tests,
- stabilize core types and pipeline contracts.

### Stage B: Must-have system

- typed sanitization,
- policy routing,
- risk-adaptive behavior,
- structured refusal,
- explainable decision flow,
- clarification path.

### Stage C: Research differentiator

- semantic intent lock,
- intent fidelity score,
- rehydration safety checker,
- stateful deception detection,
- adversarial benchmark harness,
- comparative evaluation.

### Stage D: Future platform expansion

- transport generalization,
- broader adapters,
- dashboard and UX,
- packaging and distribution polish.

---

## 7. Spec generation blueprint

This section is the operating plan for turning the rewrite into actual specs.

This document should be treated as the single source of truth for:

- what belongs in the rewrite,
- what must be implemented now,
- what is a standing engineering rule,
- what can be deferred,
- and what each next spec is responsible for.

### 7.1 Rule for creating new specs

Every new spec created from this roadmap must do all of the following:

- reference this roadmap and the package restructure design,
- declare whether it is foundation, must-have, research, or future-expansion work,
- state what previous spec it depends on,
- state what roadmap items it closes,
- state what items it explicitly leaves for later specs,
- include documentation and walkthrough updates in scope.

### 7.2 Standing rules for every spec

These are not optional and should be inherited by every spec unless explicitly overridden by an approved architectural decision.

- Python 3.11+ baseline.
- `ruff`, `pytest`, and `mypy` are mandatory quality gates.
- Use interfaces and protocols to preserve contracts.
- Use proper typed models at every important boundary.
- Validate data at configuration, API, pipeline, and adapter junctions.
- OTEL and structured logging start from day one, including simple flows.
- Document exception handling rules clearly.
- Document concurrency and thread-safety expectations clearly.
- Check whether a strong open-source library exists before custom implementation.
- Update docs and walkthrough notes as part of the spec work.

These rules should be copied into future specs as standing constraints, not rediscovered each time.

### 7.3 What does not need its own spec

The following do not need separate standalone specs unless they become large enough to justify one:

- Ruff, pytest, mypy, and Python standards.
- OTEL baseline requirements.
- structured logging conventions.
- interface-first rules.
- validation-at-boundaries rules.
- documentation and walkthrough obligations.
- adopt-vs-build library review.

These should be treated as cross-cutting requirements across all rewrite specs.

---

## 8. Planned spec sequence

The rewrite can be covered cleanly in six follow-on specs after the existing `001-arc-guard-rails` baseline.

### Spec 002 — Rewrite foundation

Category:
foundation

Owns:

- package split into `common`, `core`, and `api`,
- contract layer and interface definitions,
- model boundaries,
- validation rules,
- exception policy,
- concurrency policy,
- enterprise Python standards,
- open-source library review before advanced implementation.

Does not own:

- semantic fidelity features,
- advanced jailbreak statefulness,
- transport expansion.

### Spec 003 — Sanitization and policy core

Category:
must-have

Owns:

- typed placeholder sanitization,
- composable policy routing,
- risk-adaptive behavior,
- graceful refusal,
- clarification-first control flow,
- explainable decision records.

Does not own:

- semantic intent lock,
- fidelity scoring,
- multi-turn deception memory.

### Spec 004 — Observability and runtime hardening

Category:
must-have

Owns:

- OTEL setup and instrumentation,
- structured logging schema,
- flow-level spans and metrics,
- runtime failure handling,
- thread-safety and async runtime hardening,
- logging of every important stage in the flow.

Does not own:

- core research novelty,
- broader transport support.

### Spec 005 — Safe rehydration and intent fidelity

Category:
research contribution

Owns:

- semantic intent lock,
- intent fidelity score,
- rehydration safety checker,
- fidelity-aware warning, refusal, or clarification thresholds,
- semantic verification of rehydrated output.

This is the primary thesis differentiator spec.

### Spec 006 — Jailbreak, deception, and evaluation

Category:
research contribution

Owns:

- stronger jailbreak detection,
- stateful deception detection,
- adversarial prompt corpora,
- comparative evaluation harness,
- baseline-vs-guarded measurement framework.

### Spec 007 — Integration, API, and documentation completion

Category:
delivery and polish

Owns:

- API package wiring,
- reusable library surface cleanup,
- integration notes,
- walkthrough maintenance,
- doc consolidation,
- explicit backlog capture for future transports, dashboards, and packaging polish.

---

## 9. Coverage map

This map shows how the roadmap is fully covered so nothing is left ownerless.

### 9.1 First things

| Roadmap item | Owner |
|---|---|
| Lock rewrite boundary | Spec 002 |
| Fix package boundaries | Spec 002 |
| Preserve current code as migration source | Spec 002 |
| Define baseline pipeline | Spec 003 |
| Build evaluation harness early | Spec 006 |
| Engineering standards from day zero | Standing rule across Specs 002-007 |
| Validate data at every boundary | Standing rule, implemented first in Spec 002 and expanded in later specs |
| OTEL, logging, exceptions, concurrency | Standing rule, implemented structurally in Spec 004 |
| Reuse before build | Standing rule, first applied in Spec 002 |
| Use project tools deliberately | Standing rule across Specs 002-007 |
| Documentation is part of the rewrite | Standing rule, operationalized strongly in Spec 007 |

### 9.2 Must-have features

| Roadmap item | Owner |
|---|---|
| Structured entity sanitization | Spec 003 |
| Composable policy routing | Spec 003 |
| Risk-adaptive behavior | Spec 003 |
| Graceful refusal envelope | Spec 003 |
| Explainable guardrail decisions | Spec 003 and Spec 004 |
| Clarification path | Spec 003 |
| Observability and evaluation hooks | Spec 004 |

### 9.3 Research contribution features

| Roadmap item | Owner |
|---|---|
| Semantic intent lock | Spec 005 |
| Intent fidelity score | Spec 005 |
| Rehydration safety checker | Spec 005 |
| Stateful jailbreak and deception detection | Spec 006 |
| Adversarial evaluation harness | Spec 006 |
| Fidelity-oriented metrics | Spec 005 and Spec 006 |

### 9.4 Nice-to-have features

| Roadmap item | Owner |
|---|---|
| More transports | Future backlog, recorded in Spec 007 |
| More provider integrations | Future backlog, recorded in Spec 007 |
| Rich policy authoring UX | Future backlog, recorded in Spec 007 |
| Product dashboard and analytics UI | Future backlog, recorded in Spec 007 |
| Advanced packaging polish | Future backlog, recorded in Spec 007 |

### 9.5 What not to start yet

These remain explicit guardrails on planning, not implementation work:

- do not start broad transport expansion before the core rewrite stabilizes,
- do not lead with dashboards,
- do not inflate policy DSL work without evaluation,
- do not treat regex-only growth as the main novelty,
- do not spend early cycles on packaging polish ahead of the thesis differentiator.

---

## 10. Exit criteria for each new spec

Before a spec is considered complete, it should satisfy all of the following:

- closes the roadmap items assigned to it,
- does not silently absorb items owned by later specs,
- includes docs and walkthrough updates,
- preserves interfaces and typed model boundaries,
- leaves a clear handoff to the next spec.

If a task appears during planning and it is not clearly mapped to a current spec, it should be added back into this roadmap first before starting work.

---

## 11. Reminder to future self

When priorities become unclear, come back to this test:

Does this feature clearly improve one or more of these?

- privacy preservation,
- adversarial resistance,
- semantic fidelity.

If not, it is probably not part of the first rewrite.

The project does not need to impress by being huge. It needs to impress by having a clear thesis contribution and a disciplined architecture.
