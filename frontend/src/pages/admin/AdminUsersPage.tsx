import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { changeBlock, changeRole, listUsers } from "@/api/users";
import type { UserRole } from "@/api/types";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/form";

const SIZE = 20;
const ROLES: UserRole[] = ["participant", "judge", "admin"];
const ROLE_LABELS: Record<UserRole, string> = {
  participant: "Участник",
  judge: "Судья",
  admin: "Администратор",
};

export function AdminUsersPage() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1") || 1;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["users", page],
    queryFn: () => listUsers(page, SIZE),
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  const setRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      changeRole(userId, role),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const setBlock = useMutation({
    mutationFn: ({ userId, blocked }: { userId: string; blocked: boolean }) =>
      changeBlock(userId, blocked),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  function go(next: number) {
    const merged = new URLSearchParams(params);
    merged.set("page", String(next));
    setParams(merged);
  }

  const items = query.data ?? [];
  const hasNext = items.length === SIZE;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Пользователи</h1>

      {error && <Alert variant="error">{error}</Alert>}
      {query.isLoading && <p className="text-sm text-muted-foreground">Загрузка…</p>}
      {query.isError && <Alert variant="error">{errorMessage(query.error)}</Alert>}

      {query.data && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Имя</th>
                <th>Email</th>
                <th className="w-44">Роль</th>
                <th className="w-28">Статус</th>
                <th className="w-40">Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((user) => (
                <tr key={user.id}>
                  <td>{user.name}</td>
                  <td>{user.email}</td>
                  <td>
                    <Select
                      value={user.role}
                      disabled={setRole.isPending}
                      onChange={(event) =>
                        setRole.mutate({ userId: user.id, role: event.target.value as UserRole })
                      }
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {ROLE_LABELS[role]}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td>
                    {user.is_blocked ? (
                      <Badge variant="danger">Заблокирован</Badge>
                    ) : (
                      <Badge variant="success">Активен</Badge>
                    )}
                  </td>
                  <td>
                    <Button
                      variant={user.is_blocked ? "secondary" : "danger"}
                      size="sm"
                      disabled={setBlock.isPending}
                      onClick={() =>
                        setBlock.mutate({ userId: user.id, blocked: !user.is_blocked })
                      }
                    >
                      {user.is_blocked ? "Разблокировать" : "Заблокировать"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center gap-3 text-sm">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => go(page - 1)}>
              Назад
            </Button>
            <span className="text-muted-foreground">Страница {page}</span>
            <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => go(page + 1)}>
              Вперёд
            </Button>
          </div>
        </>
      )}

      <Link to="/admin/contests" className="text-sm">
        К конкурсам
      </Link>
    </div>
  );
}
