import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext, type AuthContextValue } from "@/auth/context";
import { LoginPage } from "./LoginPage";

function renderLogin(login: AuthContextValue["login"]) {
  const value: AuthContextValue = {
    user: null,
    status: "anonymous",
    login,
    register: async () => undefined,
    loginWithGitHub: async () => undefined,
    logout: async () => undefined,
    reload: async () => undefined,
    hasRole: () => false,
  };
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={value}>
        <LoginPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  it("does not submit an empty form", async () => {
    const login = vi.fn();
    renderLogin(login);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByText("Введите email")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("rejects a malformed email", async () => {
    const login = vi.fn();
    renderLogin(login);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email"), "not-an-email");
    await user.type(screen.getByLabelText("Пароль"), "secret1");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByText("Некорректный email")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });
});
