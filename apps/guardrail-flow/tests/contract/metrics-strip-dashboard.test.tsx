import { MetricsStrip } from "@/components/explorer/MetricsStrip";
import { narrowRequestPage } from "@/lib/api/shapes";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import requestsFixture from "../../fixtures/requests.json";

vi.mock("reaviz", () => ({
  AreaSparklineChart: () => <div data-testid="sparkline" />,
  FunnelChart: () => <div data-testid="funnel-chart" />,
  FunnelSeries: () => null,
}));

describe("MetricsStrip dashboard panels", () => {
  it("keeps the funnel and replaces redundant pies with richer panels", () => {
    const page = narrowRequestPage(requestsFixture);

    render(<MetricsStrip rows={page.items} totalMatching={page.total} />);

    expect(screen.getByText("Funnel")).toBeInTheDocument();
    expect(screen.getByTestId("funnel-chart")).toBeInTheDocument();
    expect(screen.getByText("Live by stage")).toBeInTheDocument();
    expect(screen.getByText("Action × Risk")).toBeInTheDocument();
    expect(screen.getByText("Refusal codes")).toBeInTheDocument();
    expect(screen.getByText("Peak/min")).toBeInTheDocument();
    expect(screen.getByText("Active stages")).toBeInTheDocument();
    expect(screen.getByText("Block/refuse")).toBeInTheDocument();
    expect(screen.getByText("Unique codes")).toBeInTheDocument();
    expect(screen.getAllByText("Execute").length).toBeGreaterThan(0);
    expect(screen.getByText("JAILBREAK")).toBeInTheDocument();
  });

  it("preserves action and risk filter affordances", async () => {
    const page = narrowRequestPage(requestsFixture);
    const onActionFilter = vi.fn();
    const onRiskFilter = vi.fn();
    const user = userEvent.setup();

    render(
      <MetricsStrip
        rows={page.items}
        totalMatching={page.total}
        onActionFilter={onActionFilter}
        onRiskFilter={onRiskFilter}
      />,
    );

    await user.click(screen.getAllByTitle('Filter table to action "block"')[0]!);
    await user.click(screen.getByTitle('Filter table to risk "high"'));

    expect(onActionFilter).toHaveBeenCalledWith("block");
    expect(onRiskFilter).toHaveBeenCalledWith("high");
  });

  it("keeps matrix totals pinned to the loaded slice when action filters are active", () => {
    const page = narrowRequestPage(requestsFixture);
    const filteredRows = page.items.filter((row) => row.final_action === "block");

    render(
      <MetricsStrip
        rows={filteredRows}
        matrixRows={page.items}
        totalMatching={filteredRows.length}
        activeActionFilters={["block"]}
        onActionFilter={vi.fn()}
        onRiskFilter={vi.fn()}
      />,
    );

    const highRiskButton = screen.getByTitle('Filter table to risk "high"');
    expect(highRiskButton).toHaveTextContent("3");
    expect(highRiskButton).toHaveAttribute("aria-pressed", "false");

    const blockActionButton = screen.getAllByTitle('Filter table to action "block"')[0]!;
    expect(blockActionButton).toHaveTextContent("2");
    expect(blockActionButton).toHaveAttribute("aria-pressed", "true");
  });
});
