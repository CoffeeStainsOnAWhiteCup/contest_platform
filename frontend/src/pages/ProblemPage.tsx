import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ApiError, errorMessage } from "@/api/errors";
import { getProblem } from "@/api/problems";
import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";

export function ProblemPage() {
  const { problemId = "" } = useParams();
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["problem", problemId],
    queryFn: () => getProblem(problemId),
    enabled: Boolean(problemId),
    retry: false,
  });

  if (query.isLoading) {
    return <p className="text-sm text-muted-foreground">Загрузка…</p>;
  }
  if (query.isError) {
    const unauthorized = query.error instanceof ApiError && query.error.status === 401;
    if (unauthorized && !user) {
      return (
        <Alert variant="info">
          Чтобы открыть условие задачи, <Link to="/login">войдите</Link>.
        </Alert>
      );
    }
    return <Alert variant="error">{errorMessage(query.error)}</Alert>;
  }
  if (!query.data) {
    return null;
  }

  const problem = query.data;
  const samples = problem.samples ?? [];

  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">{problem.title}</h1>
        <p className="text-sm text-muted-foreground">
          Ограничения: {problem.time_limit_ms} мс, {problem.memory_limit_mb} МБ
        </p>
      </div>

      <Card title="Условие">
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{problem.statement}</div>
      </Card>

      <Card title="Примеры">
        {samples.length === 0 ? (
          <p className="text-sm text-muted-foreground">Примеры не заданы.</p>
        ) : (
          <div className="space-y-4">
            {samples.map((sample) => (
              <div key={sample.ordinal} className="space-y-1">
                <h3 className="text-sm font-medium">Пример {sample.ordinal}</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="mb-1 text-xs text-muted-foreground">Ввод</p>
                    <pre className="overflow-x-auto rounded border border-border bg-muted p-2 font-mono text-xs">
                      {sample.input_data || " "}
                    </pre>
                  </div>
                  <div>
                    <p className="mb-1 text-xs text-muted-foreground">Вывод</p>
                    <pre className="overflow-x-auto rounded border border-border bg-muted p-2 font-mono text-xs">
                      {sample.expected_output || " "}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
