import { describe, expect, it } from "vitest";
import {
  narrowRequestDebugPage,
  narrowRequestDecisionEnvelope,
  narrowRequestPage,
  narrowRequestWorkspaceManifest,
} from "@/lib/api/shapes";

import requestsFixture from "../../fixtures/requests.json";
import sampleManifest from "../../fixtures/requests/01JFIXT0RID01.json";
import liveManifest from "../../fixtures/requests/01JFIXT0LIVE01.json";
import sampleDecision from "../../fixtures/requests/01JFIXT0RID01/decision.json";
import sampleDebug from "../../fixtures/requests/01JFIXT0RID01/debug.json";

/**
 * Contract test: every fixture parses cleanly through the TS narrowers
 * in `src/lib/api/shapes.ts`. A backend shape change that breaks dashboard
 * parsing assumptions trips this test.
 */

describe("shapes-match-backend", () => {
  it("requests.json parses as RequestPage", () => {
    expect(() => narrowRequestPage(requestsFixture)).not.toThrow();
    const page = narrowRequestPage(requestsFixture);
    expect(page.items.length).toBeGreaterThan(0);
    expect(page.items.length).toBe(page.total);
  });

  it("01JFIXT0RID01.json parses as RequestWorkspaceManifest", () => {
    expect(() => narrowRequestWorkspaceManifest(sampleManifest)).not.toThrow();
    const m = narrowRequestWorkspaceManifest(sampleManifest);
    expect(m.summary.rid).toBe("01JFIXT0RID01");
    expect(m.resources.lifecycle).toBe(true);
  });

  it("01JFIXT0LIVE01.json parses as RequestWorkspaceManifest with live=true", () => {
    expect(() => narrowRequestWorkspaceManifest(liveManifest)).not.toThrow();
    const m = narrowRequestWorkspaceManifest(liveManifest);
    expect(m.summary.live).toBe(true);
    expect(m.resources.live_stream).toBe(true);
  });

  it("decision.json parses as RequestDecisionEnvelope", () => {
    expect(() => narrowRequestDecisionEnvelope(sampleDecision)).not.toThrow();
    const d = narrowRequestDecisionEnvelope(sampleDecision);
    expect(d.rid).toBe("01JFIXT0RID01");
    expect(typeof d.decision).toBe("object");
  });

  it("debug.json parses as RequestDebugPage", () => {
    expect(() => narrowRequestDebugPage(sampleDebug)).not.toThrow();
    const d = narrowRequestDebugPage(sampleDebug);
    expect(d.rid).toBe("01JFIXT0RID01");
    expect(d.items.length).toBeGreaterThan(0);
  });

  it("requests.json includes one live row + a mix of final actions", () => {
    const page = narrowRequestPage(requestsFixture);
    const liveRows = page.items.filter((r) => r.live);
    expect(liveRows.length).toBe(1);

    const actions = new Set(page.items.map((r) => r.final_action).filter((a) => a !== null));
    // Expect coverage of at least three distinct final actions to keep the
    // explorer's filter UX exercisable from fixture mode alone.
    expect(actions.size).toBeGreaterThanOrEqual(3);
  });
});
