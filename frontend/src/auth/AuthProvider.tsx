import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { githubExchange, login as apiLogin, logout as apiLogout, register as apiRegister } from "@/api/auth";
import { getMe } from "@/api/users";
import type { Profile, UserRole } from "@/api/types";
import { AuthContext, type AuthStatus } from "./context";
import { clearTokens, getRefreshToken, getTokens, setTokens, subscribeAuth } from "./tokenStore";

function toStore(tokens: { access_token: string; refresh_token: string }) {
  return { access: tokens.access_token, refresh: tokens.refresh_token };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Profile | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const reload = useCallback(async () => {
    if (!getTokens()) {
      setUser(null);
      setStatus("anonymous");
      return;
    }
    try {
      const profile = await getMe();
      setUser(profile);
      setStatus("authenticated");
    } catch {
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(
    () =>
      subscribeAuth(() => {
        if (!getTokens()) {
          setUser(null);
          setStatus("anonymous");
        }
      }),
    [],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await apiLogin(email, password);
      setTokens(toStore(tokens));
      const profile = await getMe();
      setUser(profile);
      setStatus("authenticated");
    },
    [],
  );

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      await apiRegister(name, email, password);
      await login(email, password);
    },
    [login],
  );

  const loginWithGitHub = useCallback(async () => {
    const tokens = await githubExchange();
    setTokens(toStore(tokens));
    const profile = await getMe();
    setUser(profile);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await apiLogout(refresh);
      } catch {
        // The local session is cleared even if the server call fails.
      }
    }
    clearTokens();
    setUser(null);
    setStatus("anonymous");
  }, []);

  const hasRole = useCallback(
    (...roles: UserRole[]) => (user ? roles.includes(user.role) : false),
    [user],
  );

  const value = useMemo(
    () => ({ user, status, login, register, loginWithGitHub, logout, reload, hasRole }),
    [user, status, login, register, loginWithGitHub, logout, reload, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
