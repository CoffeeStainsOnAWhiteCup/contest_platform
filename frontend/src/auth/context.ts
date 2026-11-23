import { createContext, useContext } from "react";

import type { Profile, UserRole } from "@/api/types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export type AuthContextValue = {
  user: Profile | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  loginWithGitHub: () => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
  hasRole: (...roles: UserRole[]) => boolean;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
