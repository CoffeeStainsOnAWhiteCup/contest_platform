import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { contestLeaderboard } from "@/api/rating";
import { Scoreboard } from "@/components/Scoreboard";
import { Alert } from "@/components/ui/alert";

const SIZE = 20;

export function LeaderboardPage() {
  const { contestId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1") || 1;

  const query = useQuery({
    queryKey: ["leaderboard", contestId, page],
    queryFn: () => contestLeaderboard(contestId, page, SIZE),
    enabled: Boolean(contestId),
    staleTime: 60_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Таблица результатов</h1>
        <Link to={`/contests/${contestId}`} className="text-sm">
          К конкурсу
        </Link>
      </div>
      {query.isLoading && <p className="text-sm text-muted-foreground">Загрузка…</p>}
      {query.isError && <Alert variant="error">{errorMessage(query.error)}</Alert>}
      {query.data && (
        <Scoreboard
          board={query.data}
          onPage={(next) => {
            const merged = new URLSearchParams(params);
            merged.set("page", String(next));
            setParams(merged);
          }}
        />
      )}
    </div>
  );
}
