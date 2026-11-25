import { API_BASE } from "@/api/config";
import { ApiError } from "@/api/errors";
import { clearTokens, getTokens, setTokens, type Tokens } from "./tokenStore";

const SKEW_SECONDS = 20;

function accessTokenExpiry(token: string): number | null {
  const payload = token.split(".")[1];
  if (!payload) {
    return null;
  }
  try {
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const data = JSON.parse(json) as { exp?: number };
    return typeof data.exp === "number" ? data.exp : null;
  } catch {
    return null;
  }
}

export function isAccessTokenFresh(token: string): boolean {
  const exp = accessTokenExpiry(token);
  if (exp === null) {
    return true;
  }
  return exp - SKEW_SECONDS > Date.now() / 1000;
}

async function performRefresh(refreshToken: string): Promise<Tokens> {
  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    credentials: "include",
  });
  if (!response.ok) {
    clearTokens();
    let detail: unknown = response.statusText;
    try {
      const data = (await response.json()) as { detail?: unknown };
      detail = data.detail ?? data;
    } catch {
      // keep statusText
    }
    throw new ApiError("Не удалось обновить сессию", response.status, detail);
  }
  const data = (await response.json()) as { access_token: string; refresh_token: string };
  const tokens: Tokens = { access: data.access_token, refresh: data.refresh_token };
  setTokens(tokens);
  return tokens;
}

let inflight: Promise<string> | null = null;

async function runRefresh(): Promise<string> {
  const refresh = async (): Promise<string> => {
    const current = getTokens();
    if (!current) {
      throw new ApiError("Сессия отсутствует", 401, "NO_SESSION");
    }
    // Another tab may have refreshed while we waited for the lock.
    if (isAccessTokenFresh(current.access)) {
      return current.access;
    }
    return (await performRefresh(current.refresh)).access;
  };

  if (typeof navigator !== "undefined" && "locks" in navigator) {
    return navigator.locks.request("contest-auth-refresh", refresh);
  }
  return refresh();
}

/** Single-flight refresh shared by every tab through the Web Locks API. */
export function refreshAccessToken(): Promise<string> {
  inflight ??= runRefresh().finally(() => {
    inflight = null;
  });
  return inflight;
}
