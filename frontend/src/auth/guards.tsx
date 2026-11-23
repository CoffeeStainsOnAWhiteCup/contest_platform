import { Navigate, Outlet, useLocation } from "react-router-dom";

import type { UserRole } from "@/api/types";
import { useAuth } from "./context";

export function LoadingScreen() {
  return <p className="p-6 text-sm text-muted-foreground">Загрузка…</p>;
}

export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <LoadingScreen />;
  }
  if (status === "anonymous") {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return <Outlet />;
}

export function RequireRole({ roles }: { roles: UserRole[] }) {
  const { status, hasRole } = useAuth();

  if (status === "loading") {
    return <LoadingScreen />;
  }
  if (!hasRole(...roles)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
