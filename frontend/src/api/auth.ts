import { apiJson } from "./client";
import type { TokenResponse, UserRead } from "./types";

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiJson<TokenResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function register(name: string, email: string, password: string): Promise<UserRead> {
  return apiJson<UserRead>("/auth/register", {
    method: "POST",
    body: { name, email, password },
  });
}

export function logout(refreshToken: string): Promise<void> {
  return apiJson<void>("/auth/logout", {
    method: "POST",
    body: { refresh_token: refreshToken },
  });
}

export function githubExchange(): Promise<TokenResponse> {
  return apiJson<TokenResponse>("/auth/github/exchange", { method: "POST" });
}
