# Walkthrough — System Canvas

This page is the visual companion to [system-overview.md](./system-overview.md). It keeps the same architecture model but compresses it into diagrams that show package boundaries, request flow, and the decision ladder in one place.

## 1. Architecture canvas

```mermaid
flowchart LR
    caller[Application or SDK caller]
    operator[Operator policy and thresholds]
    convo[ConversationState]
    llm[External LLM]

    subgraph api_pkg[packages/api<br/>arc-guard-service]
        service[HTTP and deployment surface]
    end

    subgraph pip_pkg[packages/pip<br/>arc-guard]
        pipeline[GuardPipeline]
        defend[Defend and classify]
        deception[Deception inspect]
        sanitize[Sanitize and strategy application]
        route[PolicyRouter]
        verify[Verify fidelity]
        rehydrate[Rehydration verifier]
        report[Reporters and middleware]
    end

    subgraph core_pkg[packages/core<br/>arc-guard-core]
        models[GuardInput, Finding, PolicyDecision, GuardResult]
        contracts[Protocols and registries]
        config[Config, thresholds, failure policy]
        obs[Tracer, Logger, MetricSink]
    end

    subgraph eval_pkg[tooling and research]
        harness[Evaluation harness]
        corpus[Labeled adversarial corpus]
    end

    caller --> service --> pipeline
    operator --> config
    config --> pipeline
    convo --> deception

    pipeline --> defend --> deception --> sanitize --> route
    route -->|allow| llm
    llm --> verify --> rehydrate --> pipeline
    route -->|warn, clarify, or block| pipeline

    pipeline --> models
    pipeline --> contracts
    pipeline --> report --> obs

    corpus --> harness --> pipeline
```

## 2. Decision canvas

```mermaid
flowchart TD
    findings[Findings, jailbreak signals, and conversation state] --> aggregate[Aggregate policy risk]
    aggregate --> low[LOW: sanitize and continue]
    aggregate --> medium[MEDIUM: sanitize and warn]
    aggregate --> high[HIGH: partial refusal plus sanitized output]
    aggregate --> critical[CRITICAL: hard block]

    low --> verify{Fidelity score}
    medium --> verify
    high --> verify

    verify -->|healthy| rehydrate[Verify placeholder safety and rehydrate]
    verify -->|drift warning| warn[Fidelity warning]
    verify -->|needs recovery| clarify[ClarificationRequest]
    verify -->|unacceptable drift| refuse[RefusalEnvelope]

    rehydrate --> final[GuardResult with final text, decisions, and audit data]
    warn --> final
    clarify --> final
    refuse --> final
    critical --> final
```

## 3. Spec ownership canvas

```mermaid
flowchart LR
    s001[Spec 001<br/>baseline library] --> s002[Spec 002<br/>foundation and contracts]
    s002 --> s003[Spec 003<br/>sanitize and policy core]
    s003 --> s004[Spec 004<br/>observability and runtime hardening]
    s004 --> s005[Spec 005<br/>intent fidelity and safe rehydration]
    s005 --> s006[Spec 006<br/>jailbreak, deception, and evaluation]

    s002 --> contracts[Package boundaries and public contract surface]
    s003 --> routing[Typed placeholders, strategies, risk bands]
    s004 --> runtime[Telemetry, failure posture, concurrency]
    s005 --> fidelity[Intent lock, fidelity thresholds, rehydration checks]
    s006 --> research[Strong detectors, conversation state, evaluation harness]
```

## How to use this canvas

- Read [system-overview.md](./system-overview.md) first when you want the narrative explanation.
- Use this page when you need the whole architecture at a glance for review, planning, or discussion.
- Jump into the per-spec walkthroughs for the detailed behavior owned by each slice.
