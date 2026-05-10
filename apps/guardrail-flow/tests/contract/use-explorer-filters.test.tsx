import { useExplorerFilters } from "@/hooks/useExplorerFilters";
import { renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

function wrapper(initialEntry = "/") {
  return function MemoryRouterWrapper({ children }: { children: React.ReactNode }) {
    return <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>;
  };
}

describe("useExplorerFilters", () => {
  it("defaults explorer page size to 10", () => {
    const { result } = renderHook(() => useExplorerFilters(), { wrapper: wrapper() });

    expect(result.current.filters.page_size).toBe(10);
    expect(result.current.toListRequestsParams().page_size).toBe(10);
  });

  it("keeps an explicit page_size from the url", () => {
    const { result } = renderHook(() => useExplorerFilters(), {
      wrapper: wrapper("/?page_size=25&page=2"),
    });

    expect(result.current.filters.page_size).toBe(25);
    expect(result.current.filters.page).toBe(2);
  });
});
