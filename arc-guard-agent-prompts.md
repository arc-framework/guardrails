# Agent Prompts: arc-guardrails Codebase Analysis & Evolution

> **Purpose**: Feed these prompts to AI coding agents (Claude Code, Cursor, Aider, etc.) to analyze and improve the `arc-guardrails` codebase.
> **Usage**: Run each prompt independently. They are self-contained. Provide the agent access to the full `python/arc-guardrails/` directory.
> **Rule**: These prompts request ANALYSIS and RECOMMENDATIONS only — no direct code changes.

---

## Prompt 1: Universal Data Classification Architecture Audit

```
You are a senior security architect reviewing an open-source Python guardrails library called `arc-guard`.

Read the entire codebase under `python/arc-guardrails/src/arc_guard/`.

The library currently guards LLM pipelines (prompt injection, PII detection, toxic output). The goal is to evolve it into a UNIVERSAL enterprise data guardrail that can classify and enforce policies on ANY data flowing through an organization — not just LLM text.

Enterprise data comes in many forms:
- REST API request/response payloads (JSON, XML, form-data)
- Kafka / Pulsar event streams (Avro, Protobuf, JSON)
- gRPC method payloads
- Database query results
- File uploads (CSV, PDF text extraction, document content)
- Webhook payloads from third-party SaaS

The framework needs a DATA CLASSIFICATION system with levels:
- PUBLIC: No restrictions, pass-through
- INTERNAL: Basic sanitization, audit logging
- SENSITIVE: Full PII/PCI inspection, redaction/hashing enforced
- RESTRICTED: Block by default, require explicit policy override, mandatory audit trail

Each classification level should map to different inspector chains, action strategies, and reporting behaviors.

Analyze the current codebase and produce a detailed report covering:

1. **GuardInput Extensibility Gap**: How well does the current `GuardInput` / `GuardContext` model support non-text data? What needs to change to accept structured payloads (JSON objects, binary-decoded Protobuf, parsed Avro)? Propose a `ContentType` or `DataEnvelope` abstraction.

2. **Classification Layer Design**: The current pipeline has no concept of data classification. Propose where a `Classifier` protocol should sit in the pipeline (before inspectors? as a middleware? as a first-pass inspector?). Should classification be static (config-driven) or dynamic (content-sniffing)?

3. **Policy Engine Gap**: Currently, `FlagProvider` controls behavioral knobs. But classification-driven rules need a proper policy engine — "if classification=SENSITIVE AND entity_type=CREDIT_CARD, then strategy=hash AND reporter=nats". Analyze how `FlagProvider` + `ActionStrategy` selection could evolve into a declarative policy engine without breaking the existing protocol contracts.

4. **Inspector Chain Per Classification**: Currently one inspector chain runs for everything. Propose how to support different chains per classification level (e.g., PUBLIC skips all inspectors, RESTRICTED runs all + adds a blocking validator).

5. **Protocol Compatibility Report**: For each of the 7 existing `typing.Protocol` interfaces, state whether they can support the universal model as-is, need method signature changes, or need replacement. Prioritize backward compatibility.

Do NOT modify any code. Output a structured analysis document with specific file references, line numbers where relevant, and concrete interface proposals (as type stubs, not implementations).
```

---

## Prompt 2: SDK / Library Packaging & Distribution Strategy

```
You are a Python packaging expert and developer experience (DX) architect.

Read the entire `python/arc-guardrails/` directory including `pyproject.toml`, `src/arc_guard/__init__.py`, and all module directories.

The arc-guard library is currently designed as a single package with optional extras (`[semantic]`, `[nats]`, `[unleash]`, `[webhook]`, `[otel]`, `[arc]`). The vision is to make this an enterprise-grade SDK that organizations install and extend.

Analyze and recommend:

1. **Package Surface Area Audit**: Review `__init__.py` public exports. Is the public API surface clean, minimal, and well-documented? Are there internal modules leaking into the public namespace? Propose an ideal public API surface that balances simplicity for basic usage with power for enterprise customization.

2. **SDK Layering Strategy**: Should this remain a single package with extras, or should it split into:
   - `arc-guard-core` (zero deps, protocols + types + pipeline)
   - `arc-guard-presidio` (PII detection)
   - `arc-guard-semantic` (ML-based classification)
   - `arc-guard-adapters` (NATS, webhook, etc.)
   Evaluate trade-offs: monorepo single package vs multi-package. Consider install complexity, version coupling, and enterprise procurement.

3. **Extension Point DX**: How easy is it for an external developer to write a custom `Inspector`, `ActionStrategy`, or `Reporter` WITHOUT importing anything from arc-guard except protocols? Test this mentally — trace the minimal import path. Identify any hidden coupling.

4. **Configuration DX**: Review `GuardConfig` and `FlagProvider`. For an enterprise deploying this across 50 microservices, how would they manage consistent configuration? Propose a config hierarchy: env vars → config file (YAML/TOML) → remote config (Unleash) → code overrides. Does the current design support this? What's missing?

5. **Wrapper / Middleware Patterns**: For each integration target below, sketch what the wrapper/middleware API surface should look like (function signatures only, no implementation):
   - FastAPI middleware: `ArcGuardMiddleware(app, guard=..., classification=...)`
   - Kafka consumer decorator: `@arc_guard.kafka(classification="SENSITIVE")`
   - gRPC interceptor: `ArcGuardInterceptor(guard=..., classify=...)`
   - Generic function decorator: `@arc_guard.protect(classification="INTERNAL")`
   - HTTP client wrapper: `ArcGuardHttpClient(base_client, guard=...)`

6. **Versioning & Compatibility Matrix**: Recommend a versioning strategy for the protocol interfaces. If `Inspector` protocol changes, how does that affect third-party extensions? Propose a compatibility promise.

Output a structured DX analysis with concrete API signatures, import paths, and a recommended evolution roadmap.
```

---

## Prompt 3: Resilience, Failure Modes & Production Hardening

```
You are a site reliability engineer (SRE) with expertise in Python async systems and production failure analysis.

Read the full `arc-guard` codebase under `python/arc-guardrails/src/arc_guard/`, paying special attention to:
- `pipeline.py` (GuardPipeline orchestration)
- `adapters/nats_reporter.py` (async bounded queue + drain loop)
- `middleware/otel.py` (observability hooks)
- `inspectors/semantic.py` (blocking ML inference in async context)
- All error handling paths

The library is designed as fail-open (exceptions → pass-through). Analyze every failure mode:

1. **Async Safety Audit**: Trace every `await` call and every `run_in_executor` usage. Are there any paths where:
   - A coroutine is created but never awaited?
   - `run_in_executor` could deadlock under thread pool exhaustion?
   - An `asyncio.Queue` operation could block the event loop?
   - A background task (`_drain_loop`) could silently die without recovery?
   - Fire-and-forget patterns could lose events during graceful shutdown?

2. **Memory Leak Potential**: Analyze object lifecycles. Could `Finding` objects accumulate without bound? Could the `EntityRegistry` grow unbounded under hot-reload? Could `NatsReporter`'s queue leak if drain loop crashes?

3. **Concurrency Under Load**: If 1000 concurrent requests hit `GuardPipeline` simultaneously:
   - Does `PresidioInspector` share a single `AnalyzerEngine` instance safely?
   - Does `SemanticInspector`'s thread pool become a bottleneck?
   - Does `EntityRegistry`'s lock become a contention point?
   - Can `NatsReporter` keep up, and what happens when it can't?

4. **Fail-Open Verification**: Trace every `try/except` in the pipeline. For each:
   - Is the exception scope too broad (catching `Exception` when it should catch specific)?
   - Is `bypass_reason` set correctly in every path?
   - Could a fail-open path produce an inconsistent `GuardResult`?
   - Are there paths where fail-open is WRONG and fail-closed would be safer (e.g., RESTRICTED classification)?

5. **Graceful Shutdown**: Analyze what happens when the host process (e.g., Sherlock) receives SIGTERM:
   - Does `NatsReporter` drain its queue?
   - Do in-flight `GuardPipeline.pre_process()` calls complete?
   - Is there a shutdown protocol? If not, propose one.

6. **Circuit Breaker Gaps**: The spec mentions a `CircuitBreakerMiddleware` example. Evaluate whether the current middleware protocol supports proper circuit breaking (half-open state, recovery probes, per-inspector breakers).

Output a prioritized risk matrix (CRITICAL / HIGH / MEDIUM / LOW) with specific file:line references and remediation proposals. Do NOT fix the code.
```

---

## Prompt 4: Enterprise Policy Engine Design

```
You are an enterprise security policy architect familiar with OPA (Open Policy Agent), Cedar, and XACML.

Read the `arc-guard` codebase, focusing on:
- `protocols/` (all 7 protocol interfaces)
- `flags/` (StaticFlagProvider, EnvFlagProvider)
- `pipeline.py` (how inspectors and strategies are selected)
- `config.py` (GuardConfig)
- `types.py` (GuardResult, Finding, RiskLevel)

Currently, arc-guard has a flat model: one inspector chain, one action strategy selected by a flag. Enterprise customers need:

- Data classification labels (PUBLIC, INTERNAL, SENSITIVE, RESTRICTED) that determine which rules apply
- Per-classification policy rules: "if SENSITIVE + CREDIT_CARD found → hash; if SENSITIVE + INJECTION → block"
- Per-entity override rules: "AADHAAR numbers are always RESTRICTED regardless of classification"
- Audit requirements per classification: "RESTRICTED always reports to NATS + webhook; PUBLIC only logs"
- Policy versioning and hot-reload without restart
- Policy evaluation audit trail (which rules fired, why)

Analyze and propose:

1. **Policy Model**: Define the data model for a policy rule. Should it be:
   - Declarative YAML/JSON (like Kubernetes RBAC policies)?
   - Code-based (like pytest fixtures)?
   - External engine (OPA/Rego sidecar)?
   Evaluate each for arc-guard's "zero network hop, in-process" philosophy.

2. **Classification → Pipeline Mapping**: How should a classification label select the inspector chain, action strategy, and reporters? Propose a `PolicyResolver` protocol that takes `(classification, findings)` and returns `(strategy, reporters, action)`.

3. **Rule Precedence & Conflict Resolution**: If two rules match (one says "redact", another says "block"), which wins? Propose a precedence model (most restrictive wins? explicit priority? rule ordering?).

4. **Integration with Existing Protocols**: Map the policy engine to existing interfaces:
   - Does `FlagProvider` become the policy source?
   - Does `ActionStrategy` selection become policy-driven?
   - Does `Reporter` selection become per-finding instead of per-pipeline?
   - Where does classification tagging happen — new protocol or middleware?

5. **Hot-Reload Without Restart**: Propose how policy updates propagate:
   - File-watch on local YAML?
   - Unleash variant payloads carrying policy JSON?
   - gRPC config stream?
   - How does this interact with `EntityRegistry`'s existing hot-reload?

6. **Audit Trail Schema**: Propose a `PolicyDecision` type that captures: rule ID, classification, matched findings, selected action, selected strategy, timestamp, pipeline duration. This should be part of `GuardResult` or a sibling.

Output a policy engine design document with type stubs, YAML schema examples for policy files, and a migration path from the current flat model to the policy-driven model. No code implementation.
```

---

## Prompt 5: Test Suite & Quality Gap Analysis

```
You are a senior QA engineer specializing in security-critical Python libraries.

Read the FULL test suite under `python/arc-guardrails/tests/` AND the source code under `src/arc_guard/`.

Cross-reference against the spec requirements:
- Coverage targets: protocols/ ≥90%, pipeline.py ≥75%, injection.py ≥90%, strategies/ ≥90%
- NFR latency targets: InjectionInspector <1ms, PresidioInspector 5-20ms, full pipeline (lite) <25ms p99
- Fail-open behavior on every inspector
- Edge cases from the spec (listed below)

Required edge cases to verify coverage:
- enabled=False → bypass_reason="disabled"
- Inspector exception → fail-open, bypass_reason="error"
- NATS unavailable → NatsReporter drops, never raises
- Reporter queue full (>1000) → drop oldest, increment metric
- SemanticInspector model not found → RuntimeError at construction
- SHERLOCK_GUARD_ENABLED=true → deprecation warning + guard activates
- Middleware.before() raises → fail-open, use original GuardInput
- Middleware.after() raises → return pre-after GuardResult
- GUARD_HASH_KEY not set → auto-generate, persist
- InjectionInspector on source="output" → skip
- SemanticInspector in lite_mode → not in chain
- Concurrent register_entity() calls → thread-safe
- HashStrategy without key → auto-generate + HMAC applied
- Overlapping PII spans in RedactStrategy → sorted desc, no double-replace

Analyze and report:

1. **Coverage Gap Matrix**: For each module, list tested vs untested code paths. Identify any edge case from the list above that has NO corresponding test.

2. **Test Quality Assessment**: Are tests testing behavior or implementation details? Are mocks appropriate or over-mocking (hiding real bugs)? Are async tests properly awaited?

3. **Missing Test Categories**:
   - Property-based tests (hypothesis) for strategy correctness?
   - Fuzzing for InjectionInspector patterns?
   - Concurrency stress tests for EntityRegistry?
   - Integration tests that wire the full pipeline end-to-end?
   - Performance regression tests (latency assertions)?

4. **Security Test Gaps**: For a security library, are there tests for:
   - Bypass attempts (crafted inputs that evade regex)?
   - Unicode normalization attacks on PII detection?
   - Timing side-channels in HashStrategy?
   - Injection patterns in non-English languages?
   - Nested/encoded payloads (base64-wrapped PII)?

5. **CI/CD Recommendations**: Propose a test matrix:
   - Fast suite (no ML models, no NATS) for every PR
   - Full suite (with models, with NATS mock) for merge to main
   - Nightly (performance benchmarks, fuzzing)

Output a structured gap analysis with specific test case descriptions (given/when/then) for every gap found. Do NOT write test code.
```

---

## Prompt 6: Multi-Transport Adapter Architecture

```
You are a distributed systems architect specializing in event-driven architectures and API gateway patterns.

Read the `arc-guard` codebase, focusing on:
- `protocols/` (Inspector, Reporter, Middleware, Guard)
- `pipeline.py` (GuardPipeline)
- `adapters/` (NatsReporter, UnleashFlagProvider)
- `types.py` (GuardInput, GuardContext)

The library currently processes text strings from LLM pipelines. The goal is to support guardrailing data across ALL enterprise transport layers:

**Inbound (request/event arrives → guard before processing):**
- REST API (FastAPI, Flask, Django) — JSON body, headers, query params
- Kafka consumer — Avro/Protobuf/JSON events from topics
- Apache Pulsar consumer — similar to Kafka but with multi-tenancy
- gRPC server — Protobuf request messages
- GraphQL resolver — query/mutation arguments
- WebSocket messages — bidirectional streaming text/binary
- File ingestion — CSV rows, PDF extracted text, document content

**Outbound (response/event leaves → guard before sending):**
- REST API response body
- Kafka/Pulsar producer — events being published
- gRPC server response
- HTTP client requests to external APIs (outbound data leakage)
- Email/notification content

Analyze and propose:

1. **Data Normalization Layer**: Design a `ContentExtractor` protocol that takes raw transport-specific input and produces a normalized `GuardPayload` that the pipeline can inspect. Different extractors for JSON, Protobuf, Avro, form-data, file content. How does this layer handle:
   - Nested JSON (guard only leaf string values? recursive descent?)
   - Protobuf fields (reflect on message descriptor? require schema?)
   - Binary content (skip? extract text? delegate to specialized inspector?)

2. **Transport Adapter Pattern**: For each transport, define the adapter surface:
   - Where does the guard hook in? (middleware, interceptor, decorator, consumer wrapper)
   - What context is available? (HTTP headers → user_id, Kafka headers → topic + partition, gRPC metadata)
   - How does classification get determined? (header? topic name convention? explicit config?)
   - What happens on "block" action? (HTTP 403? Kafka DLQ? gRPC PERMISSION_DENIED?)

3. **Streaming Data Handling**: For Kafka/Pulsar consumers processing thousands of events/second:
   - Should guard run synchronously per-event (simple but latency)?
   - Batch inspection (buffer N events, inspect batch, release)?
   - Async pipeline with backpressure?
   - Sampling strategy (inspect 10% of PUBLIC, 100% of RESTRICTED)?

4. **Bidirectional Guard Points**: For transports like gRPC and WebSocket:
   - Guard on request AND response?
   - Different classification per direction?
   - State tracking across stream lifecycle?

5. **Adapter SDK Contract**: Define the minimal interface an adapter must implement to plug into arc-guard. This should be a single protocol that any transport adapter satisfies. Propose `TransportAdapter` with methods like `extract_payload()`, `apply_action()`, `enrich_context()`.

6. **Performance Budget Per Transport**: Given the latency constraints (pipeline <25ms lite mode), analyze which transports can tolerate synchronous guarding and which need async/sampling. Propose a decision matrix.

Output an architecture document with protocol stubs, sequence diagrams (as mermaid), and a transport compatibility matrix. No implementation code.
```

---

## Prompt 7: Competitive Landscape & Differentiation Analysis

```
You are a technical product strategist analyzing the data security and AI guardrails market.

Read the full arc-guard spec, plan, and tasks documents to understand the library's architecture and capabilities.

Research and compare arc-guard against the current landscape:

1. **Direct Competitors (LLM Guardrails)**:
   - NVIDIA NeMo Guardrails
   - Guardrails AI (guardrails-ai Python package)
   - LangKit by WhyLabs
   - Lakera Guard
   - Rebuff
   - Prompt Guard (Meta)

2. **Adjacent / Enterprise DLP**:
   - Microsoft Presidio (arc-guard already uses this)
   - Google Cloud DLP
   - AWS Macie
   - Nightfall AI
   - BigID

3. **Policy Engines**:
   - Open Policy Agent (OPA)
   - AWS Cedar
   - Styra DAS

For each competitor, analyze:
- What they do well that arc-guard doesn't yet
- What arc-guard does better architecturally (protocol-first, zero network hop, fail-open, transport-agnostic vision)
- Missing features arc-guard should prioritize
- Features arc-guard should explicitly NOT build (stay focused)

Then propose:

4. **Unique Value Proposition**: What is arc-guard's "why us?" in one paragraph? Focus on the combination of: universal transport support, data classification-driven policies, in-process execution, protocol-first extensibility, and open-source.

5. **Feature Priority Matrix**: Based on competitive gaps, rank these potential features by impact vs effort:
   - Data classification engine
   - Declarative YAML policy rules
   - FastAPI/Django/Flask middleware (pip install arc-guard[fastapi])
   - Kafka/Pulsar consumer wrappers
   - gRPC interceptor
   - Visual policy editor (web UI)
   - Pre-built compliance templates (GDPR, HIPAA, PCI-DSS, India DPDPA)
   - Multi-language support (Go SDK, TypeScript SDK)
   - SaaS hosted version
   - Terraform/Helm deployment modules

6. **Naming & Positioning**: Is "arc-guard" the right name for a universal data guardrail that goes beyond AI/LLM use cases? Suggest alternatives if the scope has outgrown the name.

Output a competitive analysis document with comparison tables and a prioritized roadmap recommendation.
```

---

## Prompt 8: Observability, Audit & Compliance Deep Dive

```
You are a compliance engineer with expertise in GDPR, HIPAA, PCI-DSS, and India's DPDPA (Digital Personal Data Protection Act).

Read the `arc-guard` codebase, focusing on:
- `middleware/otel.py` (OtelMiddleware — 5 metrics, 2 spans)
- `reporters/` (LogReporter, NullReporter, WebhookReporter)
- `adapters/nats_reporter.py` (event publishing)
- `strategies/hash.py` (HMAC-SHA256)
- `strategies/redact.py` (PII replacement)
- `types.py` (Finding, GuardResult, RiskLevel)

Analyze for enterprise compliance readiness:

1. **Audit Trail Completeness**: For a compliance auditor asking "show me every time PII was detected and what action was taken in the last 90 days":
   - Does the current event schema capture enough data?
   - Is there a correlation ID linking guard events to the original request?
   - Can events be reconstructed into a timeline?
   - What's missing from the NATS event payload for compliance?

2. **GDPR / DPDPA Requirements**:
   - Right to erasure: If a user requests data deletion, can hashed PII (HMAC) be traced back and purged? (Hint: HMAC is deterministic with same key — is this a feature or a risk?)
   - Data minimization: Does the guard avoid storing raw PII in logs/events? Verify every log statement.
   - Cross-border data flow: If NatsReporter publishes to a remote NATS cluster, does that constitute data transfer?
   - Consent tracking: Should guard events link to user consent records?

3. **PCI-DSS Requirements**:
   - Is credit card detection (PresidioInspector) sufficient for PCI compliance?
   - Does HashStrategy meet PCI tokenization requirements?
   - Are there gaps in how card data flows through the pipeline (even briefly in memory)?

4. **HIPAA Considerations**:
   - PHI (Protected Health Information) detection — does Presidio cover medical record numbers, health plan IDs?
   - Are there additional entity types needed?
   - BAA (Business Associate Agreement) implications of using arc-guard as a library vs service.

5. **Observability Gaps for Enterprise**:
   - Current: 5 OTEL metrics + 2 spans. Is this enough for a security operations center (SOC)?
   - Propose additional metrics: detection rate by entity type, false positive tracking, policy override audit, classification distribution.
   - Propose additional spans: per-inspector timing, policy evaluation, strategy application.
   - Dashboard design: What should an arc-guard Grafana dashboard show?

6. **Immutable Audit Log**: Propose an audit event schema (JSON) that is:
   - Tamper-evident (signed or chained)
   - Contains: event_id, timestamp, classification, findings_summary (no raw PII), action_taken, policy_rule_id, pipeline_duration, request_correlation_id
   - Compatible with SIEM ingestion (Splunk, ELK, Datadog)

Output a compliance gap analysis with specific remediation items, proposed event schemas, and a metric catalog. No code changes.
```

---

## Prompt 9: Codebase Health & Architecture Smell Detection

```
You are a senior Python architect conducting a code quality review of a security-critical library.

Read every file in `python/arc-guardrails/src/arc_guard/` — all modules, all protocols, all adapters.

Evaluate the codebase for architecture smells, code quality, and maintainability. This is NOT a feature review — it's a structural health check.

1. **Protocol Purity**: The library claims "protocol-first, no base classes." Verify this:
   - Are there any `abc.ABC` base classes that should be protocols?
   - Are all protocols `@runtime_checkable`?
   - Can an external developer satisfy any protocol purely through structural typing with zero arc-guard imports?
   - Are protocol methods using concrete types where they should use generics?

2. **Dependency Hygiene**:
   - Trace every `import` in every file. Are there circular imports?
   - Are optional dependencies properly guarded with try/except ImportError?
   - Does `__init__.py` import too eagerly (triggering heavy deps on basic import)?
   - Is the dependency tree minimal for `pip install arc-guard` with no extras?

3. **Type Safety**:
   - Run a mental `mypy --strict` pass. Where would it complain?
   - Are there `Any` types that could be narrowed?
   - Are `TypeVar` / `Generic` used where they should be?
   - Are return types consistent across protocol implementations?

4. **Async Correctness**:
   - Are all IO-bound operations properly async?
   - Are CPU-bound operations (regex, ML inference) offloaded to executors?
   - Is `asyncio.Queue` used correctly (never blocking the event loop)?
   - Are background tasks tracked and cleaned up?

5. **Error Handling Patterns**:
   - Is the fail-open pattern consistent across ALL inspectors?
   - Are exceptions logged with enough context for debugging?
   - Are there bare `except:` or `except Exception:` that swallow important errors?
   - Is `bypass_reason` set in every error path?

6. **Naming & Conventions**:
   - Are module names, class names, and method names consistent?
   - Do file names match their primary export?
   - Is the `inspectors/` vs `strategies/` vs `reporters/` taxonomy clean?
   - Any god-objects or classes doing too much?

7. **Documentation Quality**:
   - Public APIs have docstrings? Protocols have docstrings?
   - Are docstrings accurate (not stale from refactoring)?
   - Is the README quickstart actually correct and runnable?

Output a code health scorecard (A-F grade per category) with specific file:line references for every issue found. Prioritize issues that would bite someone extending the library. No code fixes.
```

---

## Prompt 10: Developer Onboarding & Contribution Experience

```
You are a developer who has NEVER seen the arc-guard codebase before. You're evaluating it for adoption in your company's LLM platform and potentially contributing.

Read:
- `python/arc-guardrails/README.md`
- `python/arc-guardrails/pyproject.toml`
- `python/arc-guardrails/src/arc_guard/__init__.py`
- The first few files you'd naturally explore

Document your onboarding experience:

1. **First 5 Minutes**: Starting from the README:
   - Can you install and run a basic guard in under 5 minutes?
   - Is the quickstart actually quick?
   - Are error messages helpful if you're missing a dependency?
   - What confused you first?

2. **"I Want To..." Scenarios**: For each, trace the path a new developer would follow:
   - "I want to add a custom PII entity (Indian Aadhaar number)" → Which files, which protocol, how many steps?
   - "I want to write a custom inspector that checks for profanity" → Can you do this without reading the source code? Just from protocols?
   - "I want to report guard findings to Datadog instead of NATS" → How obvious is it to write a custom Reporter?
   - "I want to use arc-guard in my Flask app" → Is there guidance? A middleware? Or do you have to figure it out?
   - "I want to run arc-guard without any ML models (regex only)" → Is lite mode clearly documented? Is it the default?

3. **Contribution Path**:
   - Is there a CONTRIBUTING.md?
   - Can you run the test suite locally with a single command?
   - Are development dependencies clearly separated from runtime deps?
   - Is the CI pipeline reproducible locally?

4. **Documentation Gaps**: What questions did you have that the docs didn't answer?
   - Architecture overview / "how it all fits together" diagram?
   - Performance characteristics?
   - Upgrade/migration guide?
   - Troubleshooting section?
   - Example configurations for common deployment patterns?

5. **Comparison Shopping**: If you were comparing arc-guard to guardrails-ai or NeMo Guardrails, what would make you choose arc-guard? What would make you walk away?

Output a developer experience report card with specific pain points, missing docs, and "quick win" improvements that would dramatically improve adoption. No code changes.
```

---

## Usage Notes

**Running Order Recommendation:**
1. Start with **Prompt 9** (codebase health) — gives you a baseline
2. Then **Prompt 5** (test gaps) — validates correctness
3. Then **Prompt 3** (production hardening) — validates reliability
4. Then **Prompt 1** (universal data classification) — the big architectural evolution
5. Then **Prompt 4** (policy engine) — builds on classification
6. Then **Prompt 6** (multi-transport) — builds on universal model
7. Then **Prompt 2** (SDK packaging) — wraps it for distribution
8. Then **Prompt 8** (compliance) — enterprise readiness
9. Then **Prompt 7** (competitive analysis) — positioning
10. Finally **Prompt 10** (DX audit) — polish

**Agent Configuration Tips:**
- Give the agent READ-ONLY access to the codebase
- Set temperature low (0.1-0.3) for analysis prompts
- Allow long output (4000+ tokens) — these are deep analyses
- If using Claude Code, prefix with: `Do not edit any files. Analysis only.`
