import { ExplorerTable } from "@/components/explorer/ExplorerTable";
import { narrowRequestPage } from "@/lib/api/shapes";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import requestsFixture from "../../fixtures/requests.json";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  onPage: vi.fn(),
  onPageSizeChange: vi.fn(),
  onActionFilter: vi.fn(),
  onRiskFilter: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate,
}));

describe("ExplorerTable request console", () => {
  it("merges row details into main cells and exposes quick filters", async () => {
    const user = userEvent.setup();
    const page = narrowRequestPage(requestsFixture);

    render(
      <ExplorerTable
        page={page}
        onPage={mocks.onPage}
        onPageSizeChange={mocks.onPageSizeChange}
        onActionFilter={mocks.onActionFilter}
        onRiskFilter={mocks.onRiskFilter}
      />,
    );

    expect(screen.queryByRole("button", { name: /Show details for/ })).not.toBeInTheDocument();
    expect(screen.getByText("PII_LEAK")).toBeInTheDocument();
    expect(screen.getByText("dec_01JFIXT")).toBeInTheDocument();
    const requestCell = screen.getByText("01JFIXT0RID01").closest("td");
    expect(requestCell).not.toBeNull();
    expect(within(requestCell!).getByText(/last .*ago/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Show only block action from 01JFIXT0RID01" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Show only high risk from 01JFIXT0RID01" }),
    );
    await user.click(screen.getByRole("button", { name: "Show 25 rows per page" }));

    expect(mocks.onActionFilter).toHaveBeenCalledWith("block");
    expect(mocks.onRiskFilter).toHaveBeenCalledWith("high");
    expect(mocks.onPageSizeChange).toHaveBeenCalledWith(25);
  });

  it("opens the workspace from the inline action tray", async () => {
    const user = userEvent.setup();
    const page = narrowRequestPage(requestsFixture);

    render(
      <ExplorerTable
        page={page}
        onPage={mocks.onPage}
        onPageSizeChange={mocks.onPageSizeChange}
        onActionFilter={mocks.onActionFilter}
        onRiskFilter={mocks.onRiskFilter}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open workspace for 01JFIXT0RID01" }));

    expect(mocks.navigate).toHaveBeenCalledWith("/requests/01JFIXT0RID01");
  });
});
