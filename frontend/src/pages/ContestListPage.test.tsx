import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { ContestListPage } from "./ContestListPage";

vi.mock("@/auth/context", () => ({ useAuth: () => ({ hasRole: () => true }) }));

it("requests the displayed phase and resets pagination when switching filters", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), "http://localhost");
    const page = Number(url.searchParams.get("page"));
    const phase = url.searchParams.get("phase");
    const contest = {
      id: "contest", title: phase === "finished" ? "QA-01" : "Тренировка",
      start_at: "2020-01-01T00:00:00Z", status: "active",
      end_at: phase === "finished" ? "2021-01-01T00:00:00Z" : "2099-01-01T00:00:00Z",
    };
    return Response.json({ items: [contest], page, size: 20, total: 1 });
  });
  try {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/contests?status=active&page=2"]}>
          <ContestListPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByRole("link", { name: "Тренировка" });
    await userEvent.selectOptions(screen.getByRole("combobox"), "finished");
    await screen.findByRole("link", { name: "QA-01" });
    const urls = fetcher.mock.calls.map(([input]) => new URL(String(input), "http://localhost"));
    expect(urls.map((url) => [url.searchParams.get("phase"), url.searchParams.get("page")]))
      .toEqual([["active", "2"], ["finished", "1"]]);
    expect(urls.every((url) => !url.searchParams.has("status"))).toBe(true);
    expect(screen.getByRole("cell", { name: "Завершён" })).toBeVisible();
  } finally {
    fetcher.mockRestore();
  }
});
