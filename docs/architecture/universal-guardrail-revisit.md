# Scratch: Universal Guardrail Revisit

## 1. What I would change first

If I had one chance to reset the direction, I would **narrow the dissertation scope** and **simplify the package story**.

The current "universal guardrail" framing is useful as a product vision, but it is too broad for an academic contribution unless it is backed by a very specific research question and evaluation plan. The professor's comment is pointing in that direction.

The stronger framing is:

> How can an enterprise guardrail system sanitise sensitive user inputs before they are sent to an external LLM, detect manipulation attempts such as jailbreaks, and rehydrate the LLM response in a way that preserves the user's original intent?

That is more focused, easier to defend, and still leaves room for a broader platform later.

---

## 2. What the professor is really asking for

The comment is not rejecting the topic. It is saying three things.

### 2.1 The work is currently too derivative

Right now the proposal sounds like a systematic integration of known techniques:

- mask names and entities,
- detect prompt attacks,
- call an external LLM safely,
- restore intelligibility afterward.

That is solid engineering, but by itself it sounds like assembly rather than research.

### 2.2 The contribution is not yet sharply stated

The professor wants to know:

- What is the exact research problem?
- What is new beyond combining known components?
- How will success be measured?

### 2.3 The interesting part is not only masking, but intent preservation

The most promising part of the comment is the emphasis on:

- jailbreak sensing,
- deception resistance,
- rehydration fidelity,
- preserving the intent of the original query.

That is where the dissertation can become stronger.

---

## 3. How to make the professor happier

### 3.1 Reframe the dissertation around one core research question

Suggested question:

> Can a policy-driven sanitisation and rehydration pipeline preserve enterprise privacy while maintaining semantic fidelity and resisting adversarial prompt manipulation?

That is tighter than "universal guardrail" and gives you something measurable.

### 3.2 Make one part clearly yours

The most defensible candidate contribution is the **rehydration fidelity problem**.

Many systems redact input. Fewer systems ask:

- whether the response is still semantically aligned with the user's original intent,
- whether placeholder-based rehydration distorts meaning,
- whether a user can manipulate the guardrail by indirect instruction.

Your strongest contribution can be:

- a formal guardrail pipeline for enterprise LLM use,
- a rehydration-consistency validator,
- an evaluation method for fidelity vs privacy vs safety.

### 3.3 Add a baseline comparison

Do not evaluate the system in isolation. Compare:

1. Raw external LLM call with no sanitisation.
2. Sanitise-only pipeline.
3. Sanitise + jailbreak detection.
4. Sanitise + jailbreak detection + rehydration consistency validation.

That turns the dissertation from "we built a system" into "we measured improvement across controlled variants."

### 3.4 Use metrics the examiner can recognise

At minimum, measure:

- sensitive entity masking precision and recall,
- jailbreak detection precision and recall,
- semantic similarity between original intent and rehydrated output,
- intelligibility or task-completion score for the final response,
- latency overhead.

### 3.5 Position the broad platform as future work

Say clearly:

- the dissertation focus is enterprise prompt/response guardrailing for external LLM use,
- the wider "universal guardrail" architecture is the extensibility roadmap,
- non-LLM transports are future expansion, not the primary evaluation scope.

That makes the thesis look disciplined rather than over-ambitious.

---

## 4. Recommended package structure

If the repository should be both enterprise-friendly and open-source-friendly, the package boundaries should communicate responsibility very clearly.

I would keep the three-package idea, but with stricter rules:

- `common` is **shared infrastructure and primitives**, not domain logic.
- `core` is **all guardrail domain logic**.
- `api` is **deployment and transport surface**.

The mistake to avoid is putting "core" logic inside `common`. If `common` becomes a dumping ground, the boundaries collapse very quickly.

### 4.1 Recommended repo layout

```text
sdk/
├── packages/
│   ├── common/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── src/arc_guard_common/
│   │   │   ├── __init__.py
│   │   │   ├── errors.py
│   │   │   ├── ids.py
│   │   │   ├── enums.py
│   │   │   ├── result.py
│   │   │   ├── clock.py
│   │   │   ├── typing.py
│   │   │   ├── text/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── normalize.py
│   │   │   │   └── spans.py
│   │   │   └── utils/
│   │   │       ├── __init__.py
│   │   │       └── collections.py
│   │   └── tests/
│   │
│   ├── core/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── src/arc_guard_core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── types.py
│   │   │   ├── pipeline.py
│   │   │   ├── registry.py
│   │   │   ├── protocols/
│   │   │   ├── policies/
│   │   │   ├── inspectors/
│   │   │   │   ├── pii/
│   │   │   │   ├── injection/
│   │   │   │   ├── jailbreak/
│   │   │   │   └── semantic/
│   │   │   ├── strategies/
│   │   │   ├── rehydration/
│   │   │   ├── reporters/
│   │   │   ├── adapters/
│   │   │   ├── middleware/
│   │   │   └── refusal/
│   │   └── tests/
│   │
│   └── api/
│       ├── pyproject.toml
│       ├── README.md
│       ├── src/arc_guard_api/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── settings.py
│       │   ├── dependencies.py
│       │   ├── routes/
│       │   ├── middleware/
│       │   └── schemas/
│       └── tests/
├── docs/
├── specs/
├── scripts/
├── examples/
├── benchmarks/
└── scratch.md/
```

---

## 5. What belongs in each package

### 5.1 `common`

Keep this package small and dependency-light.

It should contain only things that are truly cross-package and not themselves "guardrail logic":

- shared exceptions,
- shared IDs and result envelopes,
- span helpers,
- text normalisation utilities,
- basic enums,
- generic utility helpers.

It should **not** contain:

- inspectors,
- strategies,
- policy routing,
- refusal decisions,
- FastAPI wiring,
- heavy observability dependencies.

Reason: once `common` contains domain concepts, everything depends on it and it becomes impossible to keep boundaries clean.

### 5.2 `core`

This is the heart of the project.

It should contain all guardrail logic:

- `GuardInput`, `GuardContext`, `GuardResult`, `Finding`,
- guard pipeline orchestration,
- policy routing,
- inspector contracts and implementations,
- strategy application,
- rehydration validation,
- refusal construction,
- reporting interfaces,
- middleware for tracing, logs, and exception boundaries.

If someone asks "is this part of the guardrail engine?", it probably belongs in `core`.

### 5.3 `api`

This package should expose the system over transport boundaries:

- FastAPI app,
- request and response schemas,
- dependency injection,
- runtime settings,
- HTTP middleware,
- service deployment concerns.

This lets open-source users consume `core` without running a service, while enterprise users can deploy `api` as a standard microservice.

---

## 6. One important correction to the current idea

The current `arc-common` package in this repo already includes:

- `structlog`,
- OpenTelemetry SDK/exporters,
- FastAPI instrumentation,
- FastAPI itself.

That means the existing `arc-common` is not a neutral `common` base for a guardrail engine.

If you reuse it as the new shared foundation, you will accidentally drag service and observability concerns into the engine boundary.

So if you adopt `common/core/api`, I would do one of these:

1. Keep existing `arc-common` as a platform support package and create a new lean `arc-guard-common`.
2. Shrink `arc-common` aggressively so it contains only dependency-light shared primitives.

Option 1 is usually safer.

---

## 7. How I would reposition "universal guardrail"

I would not throw it away. I would change its role.

### 7.1 Dissertation scope

Primary scope:

- enterprise employee query sanitisation,
- external LLM protection,
- jailbreak sensing,
- response rehydration,
- semantic fidelity validation.

### 7.2 Platform roadmap

Future scope under the same architecture:

- REST payload inspection,
- event-stream inspection,
- gRPC message inspection,
- document and file classification,
- cross-transport policy enforcement.

That keeps the architecture ambitious without making the thesis impossible to defend.

---

## 8. A cleaner story for the dissertation

If I had to rewrite the story in one paragraph, I would say this:

> This work proposes an enterprise LLM guardrail pipeline that sanitises sensitive user prompts before they are sent to external models, detects adversarial manipulation attempts such as jailbreaks, and rehydrates responses into a form that remains intelligible to the user. The main contribution is not only the integration of masking and safety checks, but a mechanism for validating whether the rehydrated response preserves the semantic intent of the original user query. The broader package architecture is designed so the same core guardrail engine can later be extended into a universal multi-transport data protection platform.

That sounds more focused, more original, and easier to evaluate.

---

## 9. Suggested implementation phases

### Phase 1: Package restructure

- split repo into `common`, `core`, `api`,
- move current engine logic into `core`,
- keep `api` thin,
- avoid mixing service dependencies into the engine.

### Phase 2: Core dissertation pipeline

- input sanitisation,
- entity masking,
- jailbreak sensing,
- response rehydration,
- structured refusal path.

### Phase 3: Research differentiator

- rehydration consistency validator,
- semantic similarity scoring,
- adversarial prompt corpus,
- baseline comparison.

### Phase 4: Universal roadmap artifacts

- generic policy model,
- transport abstraction,
- future adapter notes for HTTP, event streams, and batch data.

---

## 10. Final recommendation

Use the three-package structure, but keep the meanings strict:

- `common`: tiny, shared, non-domain primitives.
- `core`: all guardrail logic.
- `api`: service interface.

For the dissertation, do not lead with "universal guardrail" as the main claim.
Lead with:

- enterprise LLM sanitisation,
- jailbreak resistance,
- response rehydration,
- semantic fidelity.

Then present the universal guardrail architecture as the extensible design that grows out of that focused contribution.
