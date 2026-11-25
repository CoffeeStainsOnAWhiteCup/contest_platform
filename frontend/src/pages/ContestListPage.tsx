import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { listContests } from "@/api/contests";
import type { ContestStatus } from "@/api/types";
import { useAuth } from "@/auth/context";
import { Pagination } from "@/components/Pagination";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/form";
import { contestStatusLabel, contestStatusVariant } from "@/lib/labels";
import { contestPhase } from "@/lib/contestWindow";
import { useContestTime } from "@/lib/useContestTime";
import { formatDateTime } from "@/lib/format";

const SIZE = 20;

const STATUS_OPTIONS: ContestStatus[] = [
  "draft",
  "published",
  "active",
  "finished",
  "archived",
];

export function ContestListPage() {
  const { hasRole } = useAuth();
  const staff = hasRole("judge", "admin");
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1") || 1;
  const statusParam = params.get("status");
  const status =
    staff && statusParam && STATUS_OPTIONS.includes(statusParam as ContestStatus)
      ? (statusParam as ContestStatus)
      : undefined;

  const query = useQuery({
    queryKey: ["contests", page, status ?? "visible"],
    queryFn: () => listContests({ page, size: SIZE, status }),
  });

  const now = useContestTime(query.data?.items);

  function update(next: { page?: number; status?: ContestStatus | null }) {
    const merged = new URLSearchParams(params);
    if (next.page !== undefined) {
      merged.set("page", String(next.page));
    }
    if (next.status !== undefined) {
      if (next.status) {
        merged.set("status", next.status);
      } else {
        merged.delete("status");
      }
      merged.set("page", "1");
    }
    setParams(merged);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Конкурсы</h1>
        {staff && (
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            Статус публикации
            <Select
              value={status ?? ""}
              onChange={(event) =>
                update({ status: (event.target.value || null) as ContestStatus | null })
              }
            >
              <option value="">Видимые</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {contestStatusLabel(option)}
                </option>
              ))}
            </Select>
          </label>
        )}
      </div>

      {query.isLoading && <p className="text-sm text-muted-foreground">Загрузка…</p>}
      {query.isError && <Alert variant="error">{errorMessage(query.error)}</Alert>}

      {query.data && (
        <>
          {query.data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Конкурсов нет.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Название</th>
                  <th className="w-32">Статус</th>
                  <th className="w-44">Начало</th>
                  <th className="w-44">Конец</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((contest) => {
                  const phase = contestPhase(contest, now);
                  return (
                    <tr key={contest.id}>
                      <td>
                        <Link to={`/contests/${contest.id}`}>{contest.title}</Link>
                        {phase === "active" && (
                          <Badge variant="success" className="ml-2">
                            можно отправлять
                          </Badge>
                        )}
                      </td>
                      <td>
                        <Badge variant={contestStatusVariant(phase)}>
                          {contestStatusLabel(phase)}
                        </Badge>
                      </td>
                      <td>{formatDateTime(contest.start_at)}</td>
                      <td>{formatDateTime(contest.end_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <Pagination
            page={query.data.page}
            size={query.data.size}
            total={query.data.total}
            onPage={(next) => update({ page: next })}
          />
        </>
      )}
    </div>
  );
}
