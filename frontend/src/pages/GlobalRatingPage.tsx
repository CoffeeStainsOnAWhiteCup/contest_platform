import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { globalRating } from "@/api/rating";
import { Scoreboard } from "@/components/Scoreboard";
import { Alert } from "@/components/ui/alert";

const SIZE = 20;

export function GlobalRatingPage() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1") || 1;

  const query = useQuery({
    queryKey: ["rating", "global", page],
    queryFn: () => globalRating(page, SIZE),
    staleTime: 60_000,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Глобальный рейтинг</h1>
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
