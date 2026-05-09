import { describe, expect, it } from "vitest";
import { fixtureApi } from "@/lib/api/fixtures";
import { ApiError } from "@/lib/api/types";

const COMPLETED_RID = "01JFIXT0RID01";
const LIVE_RID = "01JFIXT0LIVE01";
const NONEXISTENT_RID = "01NOPE";

describe("fixture-routes-resolve", () => {
  it("listRequests returns the full fixture page", async () => {
    const page = await fixtureApi.listRequests({});
    expect(page.items.length).toBe(page.total);
    expect(page.items.length).toBeGreaterThan(0);
  });

  it("listRequests applies the rid_prefix filter", async () => {
    const page = await fixtureApi.listRequests({ rid_prefix: "01JFIXT0LIVE" });
    expect(page.items.every((r) => r.rid.startsWith("01JFIXT0LIVE"))).toBe(true);
    expect(page.items.length).toBeGreaterThan(0);
  });

  it("listRequests applies the action filter", async () => {
    const page = await fixtureApi.listRequests({ action: ["block"] });
    expect(page.items.every((r) => r.final_action === "block")).toBe(true);
  });

  it("getRequestDetail resolves for both completed and live rids", async () => {
    const completed = await fixtureApi.getRequestDetail(COMPLETED_RID);
    expect(completed.summary.rid).toBe(COMPLETED_RID);

    const live = await fixtureApi.getRequestDetail(LIVE_RID);
    expect(live.summary.live).toBe(true);
  });

  it("getRequestDetail rejects unknown rids with rid_not_found", async () => {
    await expect(fixtureApi.getRequestDetail(NONEXISTENT_RID)).rejects.toMatchObject({
      code: "rid_not_found",
    });
    await expect(fixtureApi.getRequestDetail(NONEXISTENT_RID)).rejects.toBeInstanceOf(ApiError);
  });

  it("getRequestDecision resolves for the completed rid only", async () => {
    const dec = await fixtureApi.getRequestDecision(COMPLETED_RID);
    expect(dec.rid).toBe(COMPLETED_RID);
    await expect(fixtureApi.getRequestDecision(LIVE_RID)).rejects.toMatchObject({
      code: "decision_not_captured",
    });
  });

  it("getRequestDebug resolves for both rids and rejects unknown ones", async () => {
    const debug = await fixtureApi.getRequestDebug(COMPLETED_RID, {});
    expect(debug.items.length).toBeGreaterThan(0);
    await expect(fixtureApi.getRequestDebug(NONEXISTENT_RID, {})).rejects.toMatchObject({
      code: "debug_not_captured",
    });
  });

  it("getLifecycleReplay returns events for both completed and live rids", async () => {
    const completed = await fixtureApi.getLifecycleReplay(COMPLETED_RID);
    expect(completed.events.length).toBeGreaterThan(0);
    const live = await fixtureApi.getLifecycleReplay(LIVE_RID);
    expect(live.events.length).toBeGreaterThan(0);
  });

  it("getLifecycleReplay rejects unknown rids", async () => {
    await expect(fixtureApi.getLifecycleReplay(NONEXISTENT_RID)).rejects.toMatchObject({
      code: "rid_not_found",
    });
  });
});
