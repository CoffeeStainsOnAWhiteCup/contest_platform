import { beforeEach, describe, expect, it } from "vitest";

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  getTokens,
  setTokens,
} from "./tokenStore";

describe("tokenStore", () => {
  beforeEach(() => {
    clearTokens();
  });

  it("starts empty", () => {
    expect(getTokens()).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("stores and reads both tokens", () => {
    setTokens({ access: "access-1", refresh: "refresh-1" });
    expect(getTokens()).toEqual({ access: "access-1", refresh: "refresh-1" });
    expect(getAccessToken()).toBe("access-1");
    expect(getRefreshToken()).toBe("refresh-1");
  });

  it("clears both tokens", () => {
    setTokens({ access: "access-1", refresh: "refresh-1" });
    clearTokens();
    expect(getTokens()).toBeNull();
  });
});
