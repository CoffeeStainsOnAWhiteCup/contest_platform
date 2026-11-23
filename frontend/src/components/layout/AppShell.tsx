import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/context";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

function navClass({ isActive }: { isActive: boolean }): string {
  return cn(
    "no-underline hover:no-underline",
    isActive ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
  );
}

export function AppShell() {
  const { status, user, logout } = useAuth();
  const navigate = useNavigate();

  async function onLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex h-12 w-full max-w-5xl items-center gap-5 px-4">
          <Link to="/" className="text-sm font-semibold no-underline hover:no-underline">
            Contest Platform
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <NavLink to="/contests" className={navClass}>
              Конкурсы
            </NavLink>
            <NavLink to="/rating" className={navClass}>
              Рейтинг
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-4 text-sm">
            {status === "loading" ? null : user ? (
              <>
                {user.role === "admin" && (
                  <>
                    <NavLink to="/admin/contests" className={navClass}>
                      Управление
                    </NavLink>
                    <NavLink to="/admin/users" className={navClass}>
                      Пользователи
                    </NavLink>
                  </>
                )}
                <NavLink to="/submissions" className={navClass}>
                  Решения
                </NavLink>
                <NavLink to="/profile" className={navClass}>
                  {user.name}
                </NavLink>
                <Button variant="secondary" size="sm" onClick={() => void onLogout()}>
                  Выйти
                </Button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={navClass}>
                  Войти
                </NavLink>
                <NavLink to="/register" className={navClass}>
                  Регистрация
                </NavLink>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="page flex-1">
        <Outlet />
      </main>
    </div>
  );
}
