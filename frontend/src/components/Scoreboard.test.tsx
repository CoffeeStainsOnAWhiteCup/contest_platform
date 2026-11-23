import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Board } from "@/api/types";
import { Scoreboard } from "./Scoreboard";

const board: Board = {
  items: [
    { place: 1, user_id: "u1", name: "Аня", solved: 3, penalty: 120 },
    { place: 2, user_id: "u2", name: "Борис", solved: 2, penalty: 80 },
  ],
  total: 2,
  page: 1,
  size: 20,
};

describe("Scoreboard", () => {
  it("renders every participant with their place", () => {
    render(<Scoreboard board={board} onPage={() => undefined} />);

    expect(screen.getByText("Аня")).toBeInTheDocument();
    expect(screen.getByText("Борис")).toBeInTheDocument();
    expect(screen.getByText("Страница 1 из 1 · всего 2")).toBeInTheDocument();
  });

  it("shows an empty state without entries", () => {
    render(<Scoreboard board={{ items: [], total: 0, page: 1, size: 20 }} onPage={() => undefined} />);
    expect(screen.getByText("Пока нет результатов.")).toBeInTheDocument();
  });
});
