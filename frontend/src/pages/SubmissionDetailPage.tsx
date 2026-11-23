import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { getSubmission, rejudgeSubmission } from "@/api/submissions";
import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import {
  LANGUAGE_LABELS,
  isInProgress,
  submissionLabel,
  submissionVariant,
  verdictLabel,
  verdictVariant,
} from "@/lib/labels";

function Output({ title, value }: { title: string; value: string | null | undefined }) {
  if (!value) {
    return null;
  }
  return (
    <div>
      <p className="mb-1 text-xs text-muted-foreground">{title}</p>
      <pre className="max-h-64 overflow-auto rounded border border-border bg-muted p-2 font-mono text-xs">
        {value}
      </pre>
    </div>
  );
}

export function SubmissionDetailPage() {
  const { submissionId = "" } = useParams();
  const { hasRole } = useAuth();
  const staff = hasRole("judge", "admin");
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["submission", submissionId],
    queryFn: () => getSubmission(submissionId),
    enabled: Boolean(submissionId),
    refetchInterval: (q) =>
      q.state.data && isInProgress(q.state.data.status) ? 2000 : false,
  });

  const rejudge = useMutation({
    mutationFn: () => rejudgeSubmission(submissionId),
    onSuccess: () => queryClient.invalidateQueries(),
  });

  if (query.isLoading) {
    return <p className="text-sm text-muted-foreground">Загрузка…</p>;
  }
  if (query.isError) {
    return <Alert variant="error">{errorMessage(query.error)}</Alert>;
  }
  if (!query.data) {
    return null;
  }

  const submission = query.data;
  const testResults = submission.test_results ?? [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Решение {submission.id.slice(0, 8)}</h1>
        <Badge variant={submissionVariant(submission.status)}>
          {submissionLabel(submission.status)}
        </Badge>
        {staff && !isInProgress(submission.status) && (
          <Button
            variant="secondary"
            size="sm"
            disabled={rejudge.isPending}
            onClick={() => rejudge.mutate()}
          >
            {rejudge.isPending ? "Перепроверяем…" : "Перепроверить"}
          </Button>
        )}
      </div>

      {rejudge.isError && <Alert variant="error">{errorMessage(rejudge.error)}</Alert>}

      <Card title="Сводка">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">Язык</dt>
            <dd>{LANGUAGE_LABELS[submission.language]}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Тесты</dt>
            <dd>
              {submission.passed_tests}/{submission.total_tests}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Время</dt>
            <dd>{submission.time_ms ?? "—"} мс</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Память</dt>
            <dd>{submission.memory_kb ?? "—"} КБ</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Отправлено</dt>
            <dd>{formatDateTime(submission.created_at)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Проверено</dt>
            <dd>{formatDateTime(submission.judged_at)}</dd>
          </div>
        </dl>
      </Card>

      <Card title="Вывод">
        {submission.compile_output || submission.runtime_output || submission.error_message ? (
          <div className="space-y-3">
            <Output title="Компиляция" value={submission.compile_output} />
            <Output title="Вывод программы" value={submission.runtime_output} />
            <Output title="Ошибка" value={submission.error_message} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Сообщений нет.</p>
        )}
      </Card>

      {staff && testResults.length > 0 && (
        <Card title="Результаты по тестам">
          <table className="table">
            <thead>
              <tr>
                <th className="w-16">Тест</th>
                <th className="w-56">Вердикт</th>
                <th className="w-24">Время</th>
                <th className="w-24">Память</th>
              </tr>
            </thead>
            <tbody>
              {testResults.map((result) => (
                <tr key={result.test_id}>
                  <td>{result.ordinal}</td>
                  <td>
                    <Badge variant={verdictVariant(result.status)}>
                      {verdictLabel(result.status)}
                    </Badge>
                  </td>
                  <td>{result.time_ms ?? "—"} мс</td>
                  <td>{result.memory_kb ?? "—"} КБ</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Link to="/submissions" className="text-sm">
        Ко всем решениям
      </Link>
    </div>
  );
}
