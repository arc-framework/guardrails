# Feature Specification: Sanitization and Policy Core

**Feature Branch**: `003-sanitization-policy-core`
**Created**: 2026-05-01
**Status**: Draft
**Input**: User description: "USE REWRITE ROADMAP §2 + §8.3 TO START SPEC 003 — Sanitization and Policy Core"

## Roadmap Alignment *(mandatory for rewrite specs)*

- **Roadmap reference**: [`docs/superpowers/specs/2026-05-01-rewrite-roadmap.md`](../../docs/superpowers/specs/2026-05-01-rewrite-roadmap.md) §2 (must-have features) and §8.3 (Spec 003 ownership)
- **Restructure reference**: `docs/superpowers/specs/2026-04-20-packages-restructure-design.md`
- **Category**: must-have
- **Depends on**: Spec 002 (`002-rewrite-foundation`) — consumes its contracts (`GuardInput`, `GuardResult`, `Finding`, `PolicyDecision`, `RefusalEnvelope`, `RefusalCode`), Protocols (`Inspector`, `ActionStrategy`, `Reporter`, `FlagProvider`, `EntityProvider`, `Middleware`, `Guard`), the typed exception hierarchy, the configuration schema (`GuardConfig`), and the observability hook surface (`Tracer`, `Logger`, `MetricSink`).
- **Roadmap items closed by this spec**:
  - §2.1 Structured entity sanitization (typed placeholders like `[EMPLOYEE_NAME]`, `[CUSTOMER_NAME]`, `[INTERNAL_PROJECT]`, `[CONFIDENTIAL_LOCATION]`).
  - §2.2 Composable policy routing (multiple findings → multiple strategies in one run).
  - §2.3 Risk-adaptive behavior (low / medium / high / critical thresholds).
  - §2.4 Graceful refusal envelope (machine- and human-readable).
  - §2.5 Explainable guardrail decisions (what was detected, what was masked, what fired, why).
  - §2.6 Clarification path instead of only hard refusal.
  - §1.4 Define the baseline pipeline (sanitize → defend → generate → verify-and-rehydrate) — this spec wires the sanitize stage and the policy-routing skeleton; defend / generate / verify-and-rehydrate stages are seeded as documented hooks for Specs 005/006.
- **Roadmap items partially seeded (handed to later specs)**:
  - §1.4 baseline pipeline → defend / generate / verify-and-rehydrate stages handed to Spec 005 (intent fidelity) and Spec 006 (jailbreak / deception). This spec ensures their hook points exist on the policy decision contract without prescribing semantics.
  - §3.1–3.3 Semantic intent lock / intent fidelity score / rehydration safety checker → Spec 005. This spec produces sanitized text and decision records; it does NOT compute fidelity scores or perform intent-aware rehydration.
  - §3.4 Stateful jailbreak and deception detection → Spec 006. This spec routes findings raised by jailbreak inspectors but does not own multi-turn detection.
- **Items explicitly left for later specs**:
  - Semantic intent lock, intent fidelity scoring, rehydration safety checking → Spec 005.
  - Stateful jailbreak / deception detection, adversarial corpora, comparative evaluation harness → Spec 006.
  - OTEL exporters, structured-logging schema, metrics-export wiring → Spec 004 (this spec emits events through the `Tracer` / `Logger` / `MetricSink` hooks Spec 002 stubbed; Spec 004 supplies concrete backends).
  - API package wiring beyond the existing scaffold, integration notes, future-transport backlog → Spec 007.

### Compatibility, Migration, and Enterprise Impact

- **Target module type**: implementation work in `packages/pip/src/arc_guard/` plus additive contract extensions in `packages/core/src/arc_guard_core/` (new typed-placeholder model, new `PolicyRouter` Protocol, new policy / strategy registries, new refusal-builder helpers).
- **Usage modes affected**: SDK (primary). Sidecar / worker / gateway / batch / CLI inherit the contracts unchanged. Spec 007 wires the API surface that consumes this layer.
- **Contract impact**: ADDITIVE only. Adds (a) a `TypedPlaceholder` enum / registry of canonical placeholder labels, (b) a `PolicyRule` and `PolicyRuleSet` configuration model, (c) a `PolicyRouter` Protocol that fans findings out to strategies, (d) a `DecisionRecord` typed model that explains a single pipeline run end-to-end, (e) a new `ClarificationRequest` typed model, and (f) one new optional field `GuardResult.clarification: ClarificationRequest | None` (per D1). The Spec 002 contract test suite catches every additive entry and requires a CHANGELOG line.
- **Migration impact**: existing Spec 002 callers that pass through the empty pipeline see no behavior change. New behavior is opt-in via `GuardConfig.policy` (the new field). Spec 001 callers using the legacy `arc_guard.pipeline` runtime chain see the existing redact / hash / block strategies routed through the new `PolicyRouter` automatically; the visible `GuardResult.action` and `findings` shapes do not change.
- **Enterprise impact**: enterprises gain typed entity sanitization (`[EMPLOYEE_NAME]` and friends) and risk-adaptive policy without adding any provider runtime dependencies. `arc-guard-core` install closure is unchanged. Offline / air-gapped operation is preserved because the policy router is pure computation over already-classified findings.

## User Scenarios & Testing *(mandatory)*

> Audience note: this is still a developer-facing library spec. "Users" here are library *integrators* (engineering teams adopting `arc-guardrails`), *contributors* (developers extending the policy / strategy system), and *operators* (security / compliance teams who write policy rules). Each story describes an observable outcome at a contract or policy boundary.

### User Story 1 - Integrator gets typed placeholders out of the box (Priority: P1)

An enterprise integrator pre-processes a user prompt that contains an employee name, a credit-card number, and a customer support ticket reference. They expect the sanitized output to contain typed placeholders that preserve the *meaning* of each entity (so the downstream LLM still understands the question) instead of generic `<MASKED>` blobs that destroy intent.

**Why this priority**: typed placeholder sanitization is the foundation of privacy preservation (constitution Principle V) and the headline differentiator named in the rewrite roadmap §2.1. Without it, the rewrite has no privacy story.

**Independent Test**: pass an input containing one PII entity, one PCI entity, and one enterprise entity into `pre_process`. Assert (a) the returned text contains exactly one `[<TYPE>]` placeholder per detected entity, (b) the placeholder labels come from the documented registry (`[EMPLOYEE_NAME]`, `[CREDIT_CARD]`, `[INTERNAL_PROJECT]`, etc.), (c) the placeholder positions match the original spans, and (d) `GuardResult.findings` carries one `Finding` per masked entity.

**Acceptance Scenarios**:

1. **Given** an input "Email Alice Johnson at alice@acme.com about project Helios", **When** the integrator runs `pre_process`, **Then** the returned text matches the pattern "Email [EMPLOYEE_NAME] at [EMAIL_ADDRESS] about project [INTERNAL_PROJECT]" and `GuardResult.findings` has exactly three entries (one per entity).
2. **Given** an input with two distinct credit-card numbers, **When** sanitization runs, **Then** each card is replaced with a *distinguishable* placeholder (e.g. `[CREDIT_CARD]` plus a stable index suffix) so the downstream LLM can refer to "the first card" vs "the second card" without leaking digits.
3. **Given** a benign input with no detected entities, **When** sanitization runs, **Then** the text is returned unchanged and `GuardResult.findings` is empty.

---

### User Story 2 - Operator authors a policy that routes findings to multiple strategies (Priority: P1)

A security operator writes a policy that says: redact emails, hash credit-card numbers (one-way HMAC for analytics), block on prompt injection, and warn on customer names. The integrator loads that policy, runs a single pipeline call, and sees all four strategies applied in one pass with one decision record explaining each finding's outcome.

**Why this priority**: composable policy routing is the second must-have. The Spec 001 pipeline supports only one global action; that is "too weak for realistic enterprise use" (roadmap §2.2). The thesis claim "guardrails can be policy-driven, not action-driven" depends on this story.

**Independent Test**: load a fixture policy with four rules. Submit one input that triggers all four. Assert the final `GuardResult` contains (a) the redacted/hashed text, (b) one `PolicyDecision` per finding naming its chosen strategy, (c) `action="block"` with a `RefusalEnvelope` because the prompt-injection rule fired, and (d) the order of decisions reflects the order findings were produced.

**Acceptance Scenarios**:

1. **Given** a policy with rules (`EMAIL_ADDRESS → redact`, `CREDIT_CARD → hash`, `INJECTION → block`, `CUSTOMER_NAME → warn`) and an input that triggers all four, **When** the pipeline runs, **Then** `GuardResult.decisions` has exactly four entries with strategies `redact`, `hash`, `block`, `warn` in finding order.
2. **Given** the same policy and an input triggering only `EMAIL` and `CUSTOMER_NAME`, **When** the pipeline runs, **Then** `action` is `"redact"` (the highest-severity non-block strategy among fired rules), the email is replaced, and the customer-name warning appears in `decisions` without affecting the text.
3. **Given** a policy with overlapping rules (e.g. an entity matched by two rules), **When** the pipeline runs, **Then** the router applies the *more restrictive* strategy and records the conflict resolution in the decision's rationale.

---

### User Story 3 - Risk-adaptive behavior modulates the response (Priority: P1)

An integrator sends three inputs: (a) one with a single low-risk entity, (b) one with several medium-risk entities, (c) one with a high-risk entity such as a US SSN, and (d) one with a critical-risk pattern (a confirmed prompt injection). The library responds *adaptively* — sanitize-and-continue, sanitize-and-warn, partial refusal, hard block + structured refusal — with the action choice driven by aggregated finding severity, not by a binary allow/block toggle.

**Why this priority**: binary allow/block is "too crude" (roadmap §2.3). Risk-adaptive behavior is what makes the library defensible as a research contribution.

**Independent Test**: feed four canned inputs (low / medium / high / critical) into a pipeline configured with the default risk-thresholds. Assert each returns the expected `action` (`pass`, `pass` with warning, partial restriction, `block`) and that the `GuardResult.refusal` envelope exists for high and critical only.

**Acceptance Scenarios**:

1. **Given** a low-risk input (one `EMAIL_ADDRESS`), **When** the pipeline runs, **Then** `action == "redact"` (sanitize and continue) and no refusal envelope is built.
2. **Given** a medium-risk input (a customer name plus a phone number), **When** the pipeline runs, **Then** `action == "redact"` and the `decisions` carry a non-empty `rationale` field flagging "medium-risk content sanitized" so the integrator can render a UI warning.
3. **Given** a high-risk input (US SSN), **When** the pipeline runs, **Then** the action is a partial restriction (e.g. `"redact"` with a `RefusalEnvelope` in `refusal` describing what was withheld) — the user gets a constrained answer, not a hard block.
4. **Given** a critical-risk input (confirmed prompt injection), **When** the pipeline runs, **Then** `action == "block"`, `text == ""`, and `refusal.code` is one of the registered critical codes (e.g. `RefusalCode.JAILBREAK`).

---

### User Story 4 - Refusal envelope is structured, machine-readable, and human-readable (Priority: P2)

When the pipeline blocks or restricts an action, the integrator receives a `RefusalEnvelope` whose contents include a registered machine-readable code, the human-readable explanation that can be displayed verbatim, the policy identifier that fired, and a non-empty list of suggested next steps. The integrator can render that envelope as JSON for an API client and as plain text for a chat UI without any post-processing.

**Why this priority**: refusal usability is the visible surface where most enterprise guardrail integrations fail. A structured refusal is what separates this library from a regex blacklist.

**Independent Test**: run an input that fires a critical-risk policy. Assert `RefusalEnvelope` is populated with all required fields, that the code is a registered `RefusalCode`, and that `human_message` and `next_steps` are non-empty strings drawn from the policy that fired (not generic boilerplate).

**Acceptance Scenarios**:

1. **Given** a critical-risk input with a configured policy whose refusal template names "next_steps: ['rephrase without naming the executive', 'request the public summary instead']", **When** the pipeline blocks, **Then** the returned `RefusalEnvelope.next_steps` is exactly that tuple.
2. **Given** a refusal where the policy provides only a code and trigger but no human message, **When** the envelope is built, **Then** the human message is auto-generated from the registered template for that code and is non-empty.
3. **Given** an integrator who serializes the envelope to JSON, **When** they `json.dumps` the model dump, **Then** the result contains `code`, `trigger`, `policy`, `human_message`, `next_steps`, and `decisions` as documented public fields.

---

### User Story 5 - Clarification-first control flow recovers borderline cases (Priority: P2)

An integrator sends a borderline input — say, a question that mentions a partial credit-card number that may or may not be PCI. Instead of a hard block, the pipeline asks for a safe reformulation: it returns a `GuardResult` with `action="pass"`, an empty text in some cases, and a clarification record (in `decisions[].rationale` or a dedicated `clarification` field) describing the safer rephrase the caller should request from the user.

**Why this priority**: clarification recovery is what turns guardrails from a friction surface into a productive collaborator (roadmap §2.6). It also generates valuable telemetry: every clarification is a near-miss the operator can analyze.

**Independent Test**: feed a borderline input that the policy classifies as "ambiguous". Assert the pipeline returns a clarification result (not a block) whose decision rationale names the suggested rephrase.

**Acceptance Scenarios**:

1. **Given** an input flagged as ambiguous by the policy router, **When** the pipeline runs, **Then** `GuardResult.action == "pass"`, `bypass_reason is None`, and the result carries a clarification request in the documented field.
2. **Given** the same input with `policy.clarification_enabled = False`, **When** the pipeline runs, **Then** the policy router falls back to its configured default (typically a hard block) — clarification is opt-in.

---

### User Story 6 - Decision record explains every run end-to-end (Priority: P2)

An auditor or compliance reviewer wants to know, for any given run, exactly what was detected, what was masked or transformed, which rule(s) fired, what action was taken, and why. The library produces a typed `DecisionRecord` that can be persisted to an audit log without containing raw sensitive payloads.

**Why this priority**: explainability is required for enterprise auditing AND for academic credibility (roadmap §2.5). Without it the system is a black box.

**Independent Test**: run an input through a pipeline configured with all default rules. Inspect the resulting `DecisionRecord`: it must list every detected finding (by `entity_type`, `inspector`, span without raw text), every applied transform (strategy id + before/after lengths), every fired policy rule (id), the final aggregate action, and a stable correlation identifier.

**Acceptance Scenarios**:

1. **Given** an input that triggers two findings and one block, **When** the pipeline runs, **Then** the resulting `DecisionRecord` lists both findings with their entity types, both transformations with strategy ids and length deltas, the blocking policy id, and a correlation id matching `GuardContext.correlation_id`.
2. **Given** the constitution rule that "Default events must avoid raw sensitive payloads", **When** the `DecisionRecord` is serialized, **Then** it contains no field that exposes the original raw text or the raw masked content — only span offsets, lengths, and ids.

---

### User Story 7 - Contributor adds a custom strategy without changing core (Priority: P3)

A contributor at an integrating organization implements a custom strategy that tokenizes credit-card numbers into a per-tenant deterministic token. They register the strategy at startup, the policy router picks it up by name, and the contributor's tests pass without touching `arc-guard-core` or the policy-router internals.

**Why this priority**: extensibility is a downstream concern, but if it does not work cleanly the library cannot serve real enterprise needs. The Protocol surface from Spec 002 is the basis; this story is the proof that it actually carries weight.

**Independent Test**: implement a `TokenizeStrategy` satisfying the `ActionStrategy` Protocol, register it with the strategy registry, write a policy that routes `CREDIT_CARD` to it, run an input, and confirm the result text contains tokens (not the original numbers) and the decision record names `tokenize` as the applied strategy.

**Acceptance Scenarios**:

1. **Given** a registered `TokenizeStrategy` and a policy with `CREDIT_CARD → tokenize`, **When** the pipeline runs an input with a credit-card number, **Then** the output text contains the strategy's token format and `GuardResult.decisions[0].strategy == "tokenize"`.
2. **Given** the same setup, **When** the contributor runs the import-graph check, **Then** their custom strategy module does not require any change to `arc_guard_core` and does not appear in `core`'s import closure.

---

### Edge Cases

- A finding's span overlaps with another finding's span (e.g. a phone number partially overlaps a US SSN regex match). The router must apply at most one mask per character range and document which finding "won" in the decision record.
- A policy rule references an entity type that no inspector produces. The configuration loader rejects the policy with a typed `ConfigCrossFieldError` naming the unknown entity type — the system never silently runs with an inert rule.
- A policy rule references a strategy name that is not registered. Same outcome: typed `ConfigCrossFieldError` at load time.
- Two rules apply to the same finding with conflicting strategies. The router picks the *more restrictive* (block > redact > tokenize > hash > warn > pass) and records the conflict resolution in the decision rationale.
- A strategy raises an exception. Per the Spec 002 contract this is fail-closed (`StrategyError` → refusal envelope). The decision record marks the strategy as failed and the user gets a structured refusal, not a partial output.
- The policy router itself raises (`PolicyRouterError`). Fail-closed — refusal envelope, no partial output.
- An input contains zero findings. The pipeline returns the original text with `action="pass"` and an empty `decisions` tuple; the decision record is built but contains only the correlation id and the empty findings list.
- An input is empty (`text == ""`). The pipeline returns immediately with `action="pass"`; sanitization, routing, and decision recording all short-circuit.
- A clarification request is generated but the caller's runtime cannot display it. The integrator sees the clarification in the structured decision record; rendering remains the caller's responsibility.
- A typed-placeholder collision: two entities of the same type appear in the same input. They get distinguishable suffixed placeholders (e.g. `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`) and the decision record names which suffix maps to which span.
- A risk classification depends on aggregating multiple low-risk findings into a higher risk band (e.g. three pieces of soft PII = effective high). The router exposes the aggregation rule in the decision rationale so the operator can audit it.

## Requirements *(mandatory)*

### Functional Requirements

#### Typed placeholder sanitization (roadmap §2.1)

- **FR-001**: A registered set of *typed placeholders* MUST be defined for the canonical enterprise entity types — at minimum `EMPLOYEE_NAME`, `CUSTOMER_NAME`, `INTERNAL_PROJECT`, `CONFIDENTIAL_LOCATION`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `US_SSN`, `IP_ADDRESS` — plus an `UNKNOWN_PII` fallback. The set is part of the public contract.
- **FR-002**: When a finding's `entity_type` matches a registered placeholder type, the redact strategy MUST replace the matched span according to D2: a single occurrence of an entity type renders as `[<TYPE>]`; multiple occurrences in the same input render as `[<TYPE>_1]`, `[<TYPE>_2]`, … in span order. Numbering resets per input. The placeholder registry is the single source of truth for the label format. Content-derived hashes (if used for analytics) live in `DecisionRecord.transforms[*].metadata`, never in the placeholder text.
- **FR-003**: The placeholder format MUST be configurable: an integrator MAY override the registry to add new types (e.g. `AADHAAR`, `NHS_NUMBER`) without modifying `arc_guard_core`.
- **FR-004**: A typed placeholder MUST NOT contain any portion of the original entity. The decision record MAY include the entity span and length, but never the raw value.

#### Composable policy routing (roadmap §2.2)

- **FR-005**: A `PolicyRouter` Protocol MUST be defined that takes a `GuardResult` (with findings populated by inspectors) and returns a sequence of `PolicyDecision` instances — one per finding (or per finding group, when the policy aggregates).
- **FR-006**: The default policy router MUST support per-entity-type routing rules (e.g. `EMAIL_ADDRESS → redact`, `CREDIT_CARD → hash`) loaded from a typed `PolicyRuleSet` configuration model.
- **FR-007**: Multiple rules MAY apply to a single finding. The router MUST resolve conflicts by selecting the most restrictive strategy (block > redact > tokenize > hash > warn > pass) and MUST record the conflict resolution in the decision's `rationale`.
- **FR-008**: Multiple findings MUST be routable to multiple strategies in a single pipeline run, producing one combined `GuardResult` with the aggregated text transform applied in span order.
- **FR-009**: The `PolicyRuleSet` configuration MUST be validated at load time. Unknown entity types or strategy names produce a typed `ConfigCrossFieldError` naming the offending field (FR-016 inherited from Spec 002).

#### Risk-adaptive behavior (roadmap §2.3)

- **FR-010**: A `RiskClassifier` MUST aggregate per-finding `RiskLevel` values into one *aggregate risk band* per pipeline run, using configurable thresholds.
- **FR-011**: The aggregate risk band MUST drive the chosen aggregate `GuardResult` shape per D3:
  - `LOW` → sanitize and continue. `action` is policy-driven (typically `"redact"` or `"tokenize"`), never `"block"`. `refusal is None`.
  - `MEDIUM` → sanitize and warn. `action` as for LOW; decision rationale flags `"warn"`. `refusal is None`.
  - `HIGH` → partial refusal. `text` carries the **fully sanitized** content. `action` is policy-driven and NOT `"block"`. `refusal` is populated with a `RefusalEnvelope` describing what was withheld and why. Caller renders both at its discretion.
  - `CRITICAL` → hard block. `action == "block"`, `text == ""`, `refusal` populated.
- **FR-012**: The risk thresholds MUST be configurable per `PolicyRuleSet`. Defaults are part of the public contract.
- **FR-013**: Aggregation rules (e.g. "three pieces of soft PII escalate to MEDIUM") MUST be configurable and recorded in the decision's `rationale` whenever they change the band.

#### Graceful refusal envelope (roadmap §2.4)

- **FR-014**: Every blocked or partially restricted action MUST return a `RefusalEnvelope` with the Spec 002 contract fields populated: `code`, `trigger`, `policy`, `human_message`, `decisions`, `next_steps`, `metadata`.
- **FR-015**: The `human_message` MUST be drawn from a registered template for the firing `RefusalCode`. Templates MAY be parameterized by the firing rule and the redacted finding spans.
- **FR-016**: `next_steps` MUST be non-empty for any envelope returned to the user. If the firing policy provides none, the registered default for that `RefusalCode` is used.
- **FR-017**: The envelope MUST be JSON-serializable using only public field names — no implementation-private fields leak.

#### Clarification-first control flow (roadmap §2.6)

- **FR-018**: When the policy router classifies a run as *ambiguous* (band equal to `PolicyRuleSet.ambiguous_threshold`, default `RiskBand.MEDIUM`; CRITICAL is never ambiguous), the router MUST emit a clarification record describing the suggested safer rephrase rather than blocking.
- **FR-019**: Clarification MUST be opt-in per policy. When `clarification_enabled` is `False`, ambiguous runs fall back to the policy's configured default (typically a hard block).
- **FR-020**: The clarification record MUST be exposed through the new public field `GuardResult.clarification: ClarificationRequest | None` (per D1). When clarification mode is enabled and the policy classifies a run as ambiguous, this field is populated; otherwise it is `None`. `ClarificationRequest` is a frozen dataclass carrying `suggested_rephrase: str`, `next_steps: tuple[str, ...]`, `triggering_rule_id: str | None`, and `metadata: dict[str, Any]`.

#### Explainable decision records (roadmap §2.5)

- **FR-021**: A typed `DecisionRecord` model MUST be produced for every pipeline run. It carries the correlation id (from `GuardContext.correlation_id` when present), the list of findings (entity types, spans, severities, source inspector — never raw text), the list of applied transformations (strategy ids, span deltas, before / after lengths), the firing policy rule ids, the aggregate action, and the aggregate risk band.
- **FR-022**: The `DecisionRecord` MUST be emitted to the configured `Logger` and `Reporter` per run, asynchronously and non-blockingly (constitution Principle V).
- **FR-023**: The `DecisionRecord` MUST contain no raw sensitive payload. Spans are reported as `(start, end, length)` triples; redacted text is reported as the placeholder, never the original.
- **FR-024**: The decision record format is part of the public contract and snapshotted by the Spec 002 contract test suite.

#### Strategy registry and extensibility

- **FR-025**: A `StrategyRegistry` MUST allow contributors to register custom strategies satisfying the `ActionStrategy` Protocol (Spec 002) by name, without modifying `arc_guard_core`.
- **FR-026**: The registry lookup MUST be deterministic, thread-safe, and validated at policy-load time (FR-009).
- **FR-027**: Built-in strategies (`redact`, `hash`, `block`, `warn`, `tokenize`) MUST be registered by default and conform to the public registered names.

#### Integration with Spec 002 contracts

- **FR-028**: All public types added by this spec (`PolicyRouter` Protocol, `PolicyRuleSet` model, `DecisionRecord` model, `TypedPlaceholder` enum / registry helpers) MUST be additive to `arc_guard_core`'s public surface and pass the Spec 002 contract test suite without breaking changes.
- **FR-029**: This spec MUST NOT modify the existing `Inspector`, `ActionStrategy`, `Reporter`, `FlagProvider`, `Middleware`, `EntityProvider`, or `Guard` Protocol shapes. Any change to those is a breaking contract change requiring the Spec 002 deprecation flow.
- **FR-030**: This spec MUST emit decision events through the Spec 002 observability hooks (`Tracer.start_span`, `Logger.event`, `MetricSink.counter` / `histogram`). Spec 004 substitutes concrete implementations; this spec writes against the null defaults.

#### Configuration and quality gates

- **FR-031**: `GuardConfig` gains a `policy: PolicyRuleSet | None` field (additive, default `None` meaning "no routing — fall through with `action="pass"`").
- **FR-032**: All new modules MUST pass `ruff`, `pytest`, and `mypy --strict` per the constitution's Enterprise Python Baseline. No new `disable_error_code` overrides.
- **FR-033**: The async-blocking lint (Spec 002 `tools/check_async_blocking.py`) MUST continue to pass — the policy router is pure sync computation.
- **FR-034**: A new contract test MUST verify the additive change set against the snapshot baselines, including the new `DecisionRecord` schema.
- **FR-035**: Documentation MUST land: a walkthrough page describing the policy authoring flow, a reference page for the typed placeholder registry, and worked examples showing each user story from the spec.

### Key Entities

- **`TypedPlaceholder`**: a registered, canonical entity-type label and its placeholder format. Carries `entity_type` (e.g. `"CREDIT_CARD"`), `placeholder_label` (e.g. `"[CREDIT_CARD]"`), and an optional `category` (`PII` / `PCI` / `ENTERPRISE` / `CUSTOM`). The registry is part of the public contract.
- **`PolicyRule`**: a single routing decision pattern. Carries `match` (entity type or pattern), `strategy` (registered strategy name), `severity_floor` (the minimum risk level required for the rule to apply), and `rationale_template` (human-readable string used in decision records and refusal envelopes).
- **`PolicyRuleSet`**: an ordered collection of `PolicyRule` entries plus risk thresholds (`low_max`, `medium_max`, `high_max`), aggregation rules, and a `clarification_enabled` flag. Loaded from configuration, validated at load time.
- **`PolicyRouter` (Protocol)**: takes a `GuardResult` and a `PolicyRuleSet`, returns a sequence of `PolicyDecision` and an aggregate action. Sync. Thread-safe. Failure mode: fail-closed.
- **`StrategyRegistry`**: thread-safe in-memory registry mapping registered strategy names (`redact`, `hash`, `block`, `warn`, `tokenize`, plus user-registered names) to `ActionStrategy` instances or factories.
- **`RiskClassifier`**: pure function that turns a sequence of findings into one aggregate risk band, using configurable thresholds and aggregation rules from the active `PolicyRuleSet`.
- **`DecisionRecord`**: typed model summarizing one pipeline run for audit. Carries `correlation_id`, `findings` (entity-type / span-only summaries), `transforms` (strategy id + length deltas), `fired_rules` (rule ids), `aggregate_action`, `aggregate_risk_band`, `clarification` (optional).
- **`RefusalTemplate`**: registered mapping from `RefusalCode` to a `human_message` template and default `next_steps` tuple. Used by the refusal builder when the firing policy does not provide its own.
- **`ClarificationRequest`**: a frozen dataclass added to `arc_guard_core.types` carrying `suggested_rephrase: str`, `next_steps: tuple[str, ...]`, `triggering_rule_id: str | None`, and `metadata: dict[str, Any]`. Exposed via the new optional `GuardResult.clarification` field (D1). Populated when policy classifies a run as ambiguous and `clarification_enabled=True`; `None` otherwise.

## Out of Scope *(mandatory for rewrite specs)*

The following are intentionally NOT delivered by this spec and MUST NOT be silently absorbed:

- Semantic intent lock, intent fidelity scoring, rehydration safety checking — Spec 005.
- Stateful jailbreak / deception detection across multiple turns — Spec 006.
- Adversarial corpora and the comparative evaluation harness — Spec 006.
- OTEL exporters, structured-logging schema, metrics-export wiring (only the *hooks* shipped by Spec 002 are exercised; concrete backends are Spec 004).
- API package wiring beyond Spec 002's scaffold, integration notes, transport backlog — Spec 007.
- New transports / adapters beyond what already ships in `pip` — Spec 007 / future backlog.
- Reintroduction of the modules trimmed in Spec 002 (NATS reporter, Unleash flag provider, OTEL middleware, semantic inspector, webhook reporter) — owned by Specs 004 / 005 / 007 per the recorded plan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an input containing five PII / PCI / enterprise entities of distinct types, the sanitized text contains exactly five typed placeholders drawn from the registered set, with zero raw entity bytes leaking into the output.
- **SC-002**: A policy with at least four rules applied to a single multi-entity input produces one combined `GuardResult` whose `decisions` list has exactly the expected number of entries in finding order — verified by an automated fixture suite covering at least eight policy / input combinations.
- **SC-003**: Risk-adaptive behavior is verified by a fixture suite of at least sixteen cases (four risk bands × four representative entity mixes) that asserts the correct aggregate `action` and refusal-envelope presence for each.
- **SC-004**: Every `RefusalEnvelope` emitted by the default policies passes a contract test that asserts non-empty `code`, `trigger`, `policy`, `human_message`, and `next_steps`. Zero envelopes ship with empty required fields.
- **SC-005**: 100% of `DecisionRecord` instances produced by the default fixture suite serialize to JSON without exposing raw sensitive payloads — verified by a contract test that scans serialized records for forbidden substrings.
- **SC-006**: Clarification mode, when enabled, recovers at least 80% of a fixture suite of "borderline" inputs (predefined ambiguous cases) into a clarification result rather than a hard block — measured against the fixture, not user behavior.
- **SC-007**: Adding a custom strategy follows a published recipe and requires zero changes to `arc_guard_core` — verified by a quickstart-style walkthrough that builds and tests a fixture custom strategy end-to-end in a clean venv.
- **SC-008**: The Spec 002 contract test suite reports the additive changes (new public types, new fields, new protocol) and requires a CHANGELOG entry; no breaking-change diff is produced.
- **SC-009**: All packages still pass `ruff`, `pytest`, and `mypy --strict` after this spec lands. No `disable_error_code` is added; the Spec 002 transitional override block on `pip` shrinks (or stays the same — never grows).
- **SC-010**: All four boundary tools (`check_import_graph.py`, `check_dependency_tree.py`, `check_async_blocking.py`, `check_adopt_vs_build.py`) continue to pass. `arc-guard-core` runtime closure is unchanged (still `pydantic` + stdlib).
- **SC-011**: A walkthrough page describing the policy authoring flow is published and discoverable from `packages/pip/README.md` and `docs/walkthrough/`.

## Assumptions

- Spec 002 contracts are stable. This spec extends them additively; any required *change* to a Spec 002 contract is escalated as a breaking-change spec amendment, not absorbed silently.
- Findings produced by the Spec 002 inspector chain (injection / presidio / custom) carry sufficient `entity_type` and `risk_level` granularity to drive the typed-placeholder registry. New entity types added by integrators register through the existing `EntityRegistry` plus the new `TypedPlaceholder` registry.
- The constitution's Principle V (non-blocking reporters, no raw payloads in events) governs decision-record emission. This spec emits records; Spec 004 wires the OTEL / structured-log backends.
- Risk thresholds chosen in this spec are *defaults*. Operators who need different banding override per `PolicyRuleSet` without modifying core. The defaults are recorded in the contract.
- Clarification mode is *opt-in*. Conservative deployments leave it off; the default `PolicyRuleSet` ships with `clarification_enabled = False` so existing Spec 002 callers see no behavior change.
- The trimmed modules from Spec 002 (NATS, Unleash, OTEL middleware, semantic inspector, webhook reporter) are NOT reintroduced here. Anyone needing them waits for the owning future spec.
- "Aggregate risk band" is computed by a pure function over findings — no external services, no model inference. This keeps Spec 003 offline-capable and consistent with the constitution.

## Dependencies

- Spec 002 (`002-rewrite-foundation`) — its contract types, Protocols, exception hierarchy, observability hooks, and contract test suite are the substrate this spec extends.
- The constitution at `.specify/memory/constitution.md` — every requirement here inherits its principles.
- `.specify/memory/patterns.md` and `.specify/memory/libraries.md` — patterns guide how new public types extend existing ones; libraries records any new runtime dependency review (none expected for this spec).

## Resolved Contract Decisions

The following decisions were taken at clarification time (2026-05-01) and are now part of the contract surface. They drive the additive changes the plan must implement.

### D1 — Clarification record placement *(was Q1)*

**Decision**: a new optional public field `GuardResult.clarification: ClarificationRequest | None` is added to the `arc_guard_core.types.GuardResult` typed model. Default `None`. The Spec 002 contract test suite catches the addition as additive and requires a CHANGELOG entry.

**Rationale**: most explicit, fully typed, easy to render. Integrators who don't opt into clarification mode see a `None` field that costs nothing. Conflating clarification with refusal (option C) would have polluted the refusal envelope's semantics.

**Implications**:
- `arc_guard_core.types.ClarificationRequest` is a new frozen dataclass — fields: `suggested_rephrase: str`, `next_steps: tuple[str, ...]`, `triggering_rule_id: str | None`, `metadata: dict[str, Any]`.
- `GuardResult` gains one optional field; FR-020 is updated to point at this field as the canonical placement.

### D2 — Typed-placeholder index suffixing *(was Q2)*

**Decision**: when the same entity type appears multiple times in one input, placeholders use a **sequential, per-type, per-input** index suffix: `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`, `[EMPLOYEE_NAME_1]`, etc. Numbering resets every input. A single occurrence remains unsuffixed (`[CREDIT_CARD]`).

**Rationale**: best preserves intent for the downstream LLM, which can refer to "the first card" vs "the second card" without seeing digits. Aligns with the thesis differentiator "intent-preserving guardrailing" (roadmap §0).

**Implications**:
- Single-occurrence placeholders are unsuffixed for readability; multiple-occurrence placeholders are suffixed `_1`, `_2`, … in span order.
- The decision record carries the mapping (which suffix maps to which span) for audit. Content-derived hashes, if useful for analytics, live in `DecisionRecord.transforms[*].metadata` — not in the placeholder text.
- FR-002 is updated with this exact format.

### D3 — Partial-refusal text contract *(was Q3)*

**Decision**: when the aggregate risk band is HIGH ("partial refusal"), `GuardResult.text` carries the **fully sanitized** text and `GuardResult.refusal` carries a populated `RefusalEnvelope` describing what was withheld and why. The caller decides how to render — either show the sanitized answer plus a banner, or fall back to the refusal envelope alone.

**Rationale**: preserves the intent-preservation property (the LLM still gets a useful sanitized prompt); gives the caller full latitude over the UI; never throws away the sanitizer's work. Option C (empty text) was the safer fallback but discards too much.

**Implications**:
- HIGH and CRITICAL bands both populate `RefusalEnvelope`. The `action` field distinguishes them: HIGH → `action != "block"` (typically `"redact"` or `"tokenize"` per the firing rule), CRITICAL → `action == "block"` with `text == ""`.
- FR-011 is updated to specify this exact behavior for HIGH.
