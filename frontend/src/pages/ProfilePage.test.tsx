import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { AuthContext, type AuthContextValue } from "@/auth/context";
import { ProfilePage } from "./ProfilePage";

vi.mock("@/api/notifications", () => ({
  telegramStatus: async () => ({ linked: false }),
  linkTelegram: vi.fn(),
}));
vi.mock("@/api/rating", () => ({
  myRating: async () => ({ place: 3, solved: 1, penalty: 1510 }),
}));

it("shows the saved photo, recovers after changing a broken URL and displays solved tasks", async () => {
  const client = new QueryClient();
  const profile = (avatar: string | null) => {
    const auth: AuthContextValue = {
      user: { id: "1", name: "Анна", role: "participant", email: "anna@example.com", avatar_url: avatar },
      status: "authenticated",
      login: vi.fn(), logout: vi.fn(), loginWithGitHub: vi.fn(), register: vi.fn(), reload: vi.fn(),
      hasRole: () => false,
    };
    return (
      <QueryClientProvider client={client}>
        <AuthContext.Provider value={auth}><ProfilePage /></AuthContext.Provider>
      </QueryClientProvider>
    );
  };

  const view = render(profile("https://example.org/first.png"));
  expect(screen.getByText("Участник")).toBeVisible();
  const photo = screen.getByRole("img", { name: "Фотография профиля" });
  expect(photo).toHaveAttribute("src", "https://example.org/first.png");
  fireEvent.error(photo);
  expect(screen.getByText(/Не удалось загрузить фото/)).toBeVisible();

  view.rerender(profile("https://example.org/new.png"));
  expect(screen.getByRole("img")).toHaveAttribute("src", "https://example.org/new.png");
  expect((await screen.findByText("Решено задач")).nextElementSibling).toHaveTextContent("1");

  view.rerender(profile(null));
  expect(screen.queryByRole("img")).toBeNull();
});
