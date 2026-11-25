import { render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { CallbackPage } from "./CallbackPage";

const exchange = vi.hoisted(() => vi.fn());
vi.mock("@/auth/context", () => ({
  useAuth: () => ({ user: null, loginWithGitHub: exchange }),
}));

beforeEach(() => {
  exchange.mockReset().mockResolvedValue(undefined);
});

function callback(path: string) {
  render(
    <StrictMode>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/auth/callback" element={<CallbackPage />} />
          <Route path="/" element={<p>Главная</p>} />
        </Routes>
      </MemoryRouter>
    </StrictMode>,
  );
}

it("displays cancellation without consuming a login ticket", () => {
  callback("/auth/callback?error=OAUTH_ACCESS_DENIED");
  expect(screen.getByText("Вы отменили вход через GitHub.")).toBeInTheDocument();
  expect(exchange).not.toHaveBeenCalled();
});

it("exchanges the ticket once when returning from GitHub", async () => {
  callback("/auth/callback");
  expect(await screen.findByText("Главная")).toBeInTheDocument();
  expect(exchange).toHaveBeenCalledTimes(1);
});
