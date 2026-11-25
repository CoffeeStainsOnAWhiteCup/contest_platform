import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { AdminContestsPage } from "./AdminContestsPage";

it("shows the current phase in management and updates the row at both time boundaries", () => {
  vi.useFakeTimers();
  const start = Date.parse("2026-11-25T14:29:00Z");
  vi.setSystemTime(start - 1000);
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  client.setQueryData(["contests", "admin", 1], {
    page: 1, size: 20, total: 1,
    items: [{ id: "qa01", title: "QA-01", status: "active",
      start_at: new Date(start).toISOString(), end_at: new Date(start + 60_000).toISOString() }],
  });
  try {
    render(<QueryClientProvider client={client}><MemoryRouter><AdminContestsPage /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByRole("cell", { name: "Ожидает старта" })).toBeVisible();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByRole("cell", { name: "Идёт" })).toBeVisible();
    act(() => vi.advanceTimersByTime(60_001));
    expect(screen.getByRole("cell", { name: "Завершён" })).toBeVisible();
  } finally {
    client.clear();
    vi.useRealTimers();
  }
});
