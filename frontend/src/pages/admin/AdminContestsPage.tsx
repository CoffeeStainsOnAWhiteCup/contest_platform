import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { deleteContest, listContests } from "@/api/contests";
import { errorMessage } from "@/api/errors";
import { Pagination } from "@/components/Pagination";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { contestStatusLabel, contestStatusVariant } from "@/lib/labels";

const SIZE = 20;

export function AdminContestsPage() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1") || 1;
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["contests", "admin", page],
    queryFn: () => listContests({ page, size: SIZE }),
  });

  const remove = useMutation({
    mutationFn: (contestId: string) => deleteContest(contestId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contests"] }),
  });

  function onDelete(contestId: string, title: string) {
    if (window.confirm(`Удалить конкурс «${title}»? Это действие необратимо.`)) {
      remove.mutate(contestId);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Управление конкурсами</h1>
        <Link to="/admin/contests/new">
          <Button size="sm">Создать конкурс</Button>
        </Link>
      </div>

      {remove.isError && <Alert variant="error">{errorMessage(remove.error)}</Alert>}
      {query.isLoading && <p className="text-sm text-muted-foreground">Загрузка…</p>}
      {query.isError && <Alert variant="error">{errorMessage(query.error)}</Alert>}

      {query.data && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Название</th>
                <th className="w-32">Статус публикации</th>
                <th className="w-44">Начало</th>
                <th className="w-44">Конец</th>
                <th className="w-40">Действия</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((contest) => (
                <tr key={contest.id}>
                  <td>
                    <Link to={`/contests/${contest.id}`}>{contest.title}</Link>
                  </td>
                  <td>
                    <Badge variant={contestStatusVariant(contest.status)}>
                      {contestStatusLabel(contest.status)}
                    </Badge>
                  </td>
                  <td>{formatDateTime(contest.start_at)}</td>
                  <td>{formatDateTime(contest.end_at)}</td>
                  <td className="space-x-2">
                    <Link to={`/admin/contests/${contest.id}/edit`} className="text-sm">
                      Изменить
                    </Link>
                    <button
                      type="button"
                      className="text-sm text-danger"
                      onClick={() => onDelete(contest.id, contest.title)}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={query.data.page}
            size={query.data.size}
            total={query.data.total}
            onPage={(next) => {
              const merged = new URLSearchParams(params);
              merged.set("page", String(next));
              setParams(merged);
            }}
          />
        </>
      )}
    </div>
  );
}
