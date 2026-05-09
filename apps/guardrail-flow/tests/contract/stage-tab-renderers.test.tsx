import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let payloadVisibility: "masked" | "visible" = "masked";

vi.mock("@/lib/state/ui-store", () => ({
  useUiStore: (selector: (state: { payloadVisibility: "masked" | "visible" }) => unknown) =>
    selector({ payloadVisibility }),
}));

import { EventRenderer } from "@/components/workspace/inspector/event-renderers";
import type { LifecycleEventBase } from "@/types/api";

function makeEvent(event_type: string, fields: Record<string, unknown>): LifecycleEventBase {
  return {
    id: `evt-${event_type}`,
    parent_id: null,
    seq: 1,
    ts: "2026-05-10T12:00:00Z",
    rid: "rid-014",
    event_type,
    ...fields,
  };
}

const CASES: ReadonlyArray<{
  name: string;
  event: LifecycleEventBase;
  expected: readonly string[];
}> = [
  {
    name: "RequestStarted",
    event: makeEvent("RequestStarted", {
      route: "/v1/chat/completions",
      model: "llama3.2",
      msg_count: 2,
      input_size_bytes: 48,
      raw_input: "sensitive prompt",
    }),
    expected: ["route", "/v1/chat/completions", "msg_count", "48", "raw_input"],
  },
  {
    name: "IntentCaptured",
    event: makeEvent("IntentCaptured", {
      encoder_id: "semantic:1",
      intent_size_bytes: 96,
    }),
    expected: ["encoder_id", "semantic:1", "intent_size_bytes", "96"],
  },
  {
    name: "InspectorRan",
    event: makeEvent("InspectorRan", {
      name: "PresidioInspector",
      duration_ms: 24,
      findings_count: 3,
    }),
    expected: ["name", "PresidioInspector", "duration_ms", "findings_count"],
  },
  {
    name: "JailbreakDetected",
    event: makeEvent("JailbreakDetected", {
      detector_id: "rule-based:1",
      category: "persona-switch",
      confidence: 0.97,
      evidence_reference: "jb-001",
    }),
    expected: ["detector_id", "persona-switch", "confidence", "jb-001"],
  },
  {
    name: "DeceptionScored",
    event: makeEvent("DeceptionScored", {
      score_value: 0.4,
      score_sentinel: null,
      band: "medium",
      turn_count: 3,
    }),
    expected: ["score_value", "0.4", "band", "medium", "turn_count"],
  },
  {
    name: "FindingProduced",
    event: makeEvent("FindingProduced", {
      entity_type: "EMAIL_ADDRESS",
      span: [5, 17],
      score: 1,
      risk_level: 3,
      inspector: "presidio",
    }),
    expected: ["entity_type", "EMAIL_ADDRESS", "[5, 17]", "presidio"],
  },
  {
    name: "SanitizationApplied",
    event: makeEvent("SanitizationApplied", {
      entity_type: "EMAIL_ADDRESS",
      placeholder: "[EMAIL_ADDRESS_1]",
      finding_id: "evt-finding",
      text_before: "alice@example.com",
      text_after: "[EMAIL_ADDRESS_1]",
    }),
    expected: ["placeholder", "[EMAIL_ADDRESS_1]", "finding_id", "before", "after"],
  },
  {
    name: "PlaceholderMapBuilt",
    event: makeEvent("PlaceholderMapBuilt", {
      placeholder_count: 2,
      entity_types: ["EMAIL_ADDRESS", "LOCATION"],
    }),
    expected: ["placeholder_count", "2", "EMAIL_ADDRESS", "LOCATION"],
  },
  {
    name: "StrategyExecuted",
    event: makeEvent("StrategyExecuted", {
      strategy: "RedactStrategy",
      finding_id: "evt-finding",
      text_after_size: 21,
      text_before: "alice@example.com",
      text_after: "[EMAIL_ADDRESS_1]",
    }),
    expected: ["strategy", "RedactStrategy", "text_after_size", "before", "after"],
  },
  {
    name: "FidelityScored",
    event: makeEvent("FidelityScored", {
      score_value: 0.91,
      score_sentinel: null,
      band: "high",
    }),
    expected: ["score_value", "0.91", "band", "high"],
  },
  {
    name: "BackendCalled",
    event: makeEvent("BackendCalled", {
      backend: "openai",
      url: "http://localhost:11434/v1/chat/completions",
      payload_msg_count: 1,
      model_config_snapshot: { model: "llama3.2", temperature: 0 },
    }),
    expected: ["backend", "openai", "payload_msg_count", "model_config.model"],
  },
  {
    name: "BackendResponded",
    event: makeEvent("BackendResponded", {
      duration_ms: 2810,
      http_status: 200,
      response_finish_reason: "stop",
      response_text: "guarded output",
      token_usage: { total: 123 },
    }),
    expected: ["duration_ms", "2810", "finish_reason", "stop", "token_usage.total"],
  },
  {
    name: "ResponseAssembled",
    event: makeEvent("ResponseAssembled", {
      response_id: "resp-1",
      finish_reason: "stop",
      arc_guard_blocked: false,
      response_text: "guarded output",
    }),
    expected: ["response_id", "resp-1", "finish_reason", "response_text"],
  },
  {
    name: "PolicyResolved",
    event: makeEvent("PolicyResolved", {
      max_risk: "HIGH",
      resolved_action: "redact",
      router: "default",
    }),
    expected: ["max_risk", "HIGH", "resolved_action", "redact"],
  },
  {
    name: "PolicyRuleEvaluated",
    event: makeEvent("PolicyRuleEvaluated", {
      rule_id: "pii-high",
      outcome: "matched",
      contributed_to_action: true,
    }),
    expected: ["rule_id", "pii-high", "outcome", "matched", "applied"],
  },
  {
    name: "DecisionEmitted",
    event: makeEvent("DecisionEmitted", {
      decision_id: "dec-1",
      action: "redact",
      max_risk: "HIGH",
      bypass_reason: "manual_override",
    }),
    expected: ["decision_id", "dec-1", "action", "redact", "manual_override"],
  },
  {
    name: "RehydrationVerified",
    event: makeEvent("RehydrationVerified", {
      verifier_id: "semantic:1",
      outcome: "verified",
      rejection_reason: null,
      text_before: "[EMAIL_ADDRESS_1]",
      text_after: "alice@example.com",
    }),
    expected: ["verifier_id", "semantic:1", "outcome", "verified", "after"],
  },
  {
    name: "RefusalProduced",
    event: makeEvent("RefusalProduced", {
      refusal_code: "PROMPT_INJECTION",
      human_message_chars: 64,
      decision_id: "dec-1",
    }),
    expected: ["refusal_code", "PROMPT_INJECTION", "human_message_chars", "64"],
  },
  {
    name: "RequestCompleted",
    event: makeEvent("RequestCompleted", {
      blocked: false,
      pre_action: "redact",
      post_action: "pass",
      total_duration_ms: 3483,
    }),
    expected: ["blocked", "false", "pre_action", "redact", "3483"],
  },
  {
    name: "RequestErrored",
    event: makeEvent("RequestErrored", {
      reason: "stale_live_sweep",
      terminated_by: "stale_live_sweeper",
      last_event_seq: 12,
    }),
    expected: ["reason", "stale_live_sweep", "terminated_by", "12"],
  },
];

describe("stage-tab renderers", () => {
  beforeEach(() => {
    payloadVisibility = "masked";
  });

  afterEach(() => {
    cleanup();
  });

  it.each(CASES)("renders $name with structured fields", ({ event, expected }) => {
    const { container } = render(<EventRenderer event={event} />);
    const text = container.textContent ?? "";

    for (const fragment of expected) {
      expect(text).toContain(fragment);
    }
  });

  it("masks payload-bearing fields by default", () => {
    const event = makeEvent("RequestStarted", {
      route: "/v1/chat/completions",
      model: "llama3.2",
      msg_count: 1,
      input_size_bytes: 16,
      raw_input: "sensitive prompt",
    });

    const { container } = render(<EventRenderer event={event} />);

    expect(container.textContent ?? "").not.toContain("sensitive prompt");
    expect(screen.queryByText("sensitive prompt")).toBeNull();
  });

  it("reveals payload-bearing fields when visibility is enabled", () => {
    payloadVisibility = "visible";
    const event = makeEvent("StrategyExecuted", {
      strategy: "RedactStrategy",
      finding_id: "evt-finding",
      text_after_size: 21,
      text_before: "alice@example.com",
      text_after: "[EMAIL_ADDRESS_1]",
    });

    render(<EventRenderer event={event} />);

    expect(screen.getByText("alice@example.com")).toBeDefined();
    expect(screen.getByText("[EMAIL_ADDRESS_1]")).toBeDefined();
  });
});
