import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { isAccessTokenFresh, refreshAccessToken } from "./refresh";
import { clearTokens, getTokens, setTokens } from "./tokenStore";

function encode(value: object): string {
  return btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function token(payload: Record<string, unknown>): string {
  return `${encode({ alg: "none" })}.${encode(payload)}.signature`;
}

const expired = () => token({ exp: Math.floor(Date.now() / 1000) - 60 });
const fresh = () => token({ exp: Math.floor(Date.now() / 1000) + 3600 });

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body,
  } as unknown as Response;
}

describe("isAccessTokenFresh", () => {
  it("rejects an expired token", () => {
    expect(isAccessTokenFresh(expired())).toBe(false);
  });

  it("accepts a token outside the clock skew", () => {
    expect(isAccessTokenFresh(fresh())).toBe(true);
  });
});

describe("refreshAccessToken", () => {
  beforeEach(() => {
    clearTokens();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("coalesces concurrent refreshes into one request", async () => {
    const next = fresh();
    setTokens({ access: expired(), refresh: "refresh-1" });
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, {
        access_token: next,
        refresh_token: "refresh-2",
        token_type: "bearer",
        expires_in: 1800,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const [first, second] = await Promise.all([refreshAccessToken(), refreshAccessToken()]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(first).toBe(next);
    expect(second).toBe(next);
    expect(getTokens()).toEqual({ access: next, refresh: "refresh-2" });
  });

  it("clears tokens when refresh is rejected", async () => {
    setTokens({ access: expired(), refresh: "refresh-1" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(401, { detail: "INVALID_REFRESH_TOKEN" })),
    );

    await expect(refreshAccessToken()).rejects.toThrow();
    expect(getTokens()).toBeNull();
  });

  it("reuses a still-valid access token without a request", async () => {
    setTokens({ access: fresh(), refresh: "refresh-1" });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(refreshAccessToken()).resolves.toBe(getTokens()?.access);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
