import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getContest } from "@/api/contests";
import { errorMessage } from "@/api/errors";
import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { contestPhase } from "@/lib/contestWindow";
import { useContestTime } from "@/lib/useContestTime";
import { formatDateTime } from "@/lib/format";
import { contestStatusLabel, contestStatusVariant } from "@/lib/labels";

export function ContestDetailPage() {
  const { contestId = "" } = useParams();
  const { hasRole } = useAuth();
  const staff = hasRole("judge", "admin");
  const admin = hasRole("admin");
  const query = useQuery({
    queryKey: ["contest", contestId],
    queryFn: () => getContest(contestId),
    enabled: Boolean(contestId),
  });

  const now = useContestTime(query.data);

  if (query.isLoading) {
    return <p className="text-sm text-muted-foreground">Загрузка…</p>;
  }
  if (query.isError) {
    return <Alert variant="error">{errorMessage(query.error)}</Alert>;
  }
  if (!query.data) {
    return null;
  }

  const contest = query.data;
  const phase = contestPhase(contest, now);

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{contest.title}</h1>
          <Badge variant={contestStatusVariant(phase)}>
            {contestStatusLabel(phase)}
          </Badge>
          {phase === "active" && <Badge variant="success">можно отправлять</Badge>}
        </div>
        <p className="text-sm text-muted-foreground">
          {formatDateTime(contest.start_at)} — {formatDateTime(contest.end_at)}
        </p>
        {contest.description && <p className="text-sm">{contest.description}</p>}
        <div className="flex items-center gap-4 text-sm">
          <Link to={`/contests/${contest.id}/leaderboard`}>Таблица результатов</Link>
          {admin && <Link to={`/admin/contests/${contest.id}/edit`}>Изменить конкурс</Link>}
        </div>
      </div>

      <Card
        title="Задачи"
        actions={
          staff ? (
            <Link to={`/admin/contests/${contest.id}/problems/new`}>
              <Button size="sm">Добавить задачу</Button>
            </Link>
          ) : undefined
        }
      >
        {contest.problems && contest.problems.length > 0 ? (
          <table className="table">
            <thead>
              <tr>
                <th className="w-12">№</th>
                <th>Название</th>
                <th className="w-28">Время</th>
                <th className="w-28">Память</th>
                {staff && <th className="w-24">Действия</th>}
              </tr>
            </thead>
            <tbody>
              {contest.problems.map((problem) => (
                <tr key={problem.id}>
                  <td>{problem.ordinal}</td>
                  <td>
                    <Link to={`/problems/${problem.id}`}>{problem.title}</Link>
                  </td>
                  <td>{problem.time_limit_ms} мс</td>
                  <td>{problem.memory_limit_mb} МБ</td>
                  {staff && (
                    <td className="space-x-2">
                      <Link to={`/admin/problems/${problem.id}/edit`} className="text-sm">
                        Изменить
                      </Link>
                      <Link to={`/admin/problems/${problem.id}/tests`} className="text-sm">
                        Тесты
                      </Link>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted-foreground">Задачи ещё не добавлены.</p>
        )}
      </Card>
    </div>
  );
}
