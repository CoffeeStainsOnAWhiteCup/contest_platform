import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { listSubmissions } from "@/api/submissions";
import { Pagination } from "@/components/Pagination";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/format";
import { LANGUAGE_LABELS, submissionLabel, submissionVariant } from "@/lib/labels";

const SIZE = 20;

export function SubmissionsPage() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1") || 1;

  const query = useQuery({
    queryKey: ["submissions", page],
    queryFn: () => listSubmissions({ page, size: SIZE }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Решения</h1>

      {query.isLoading && <p className="text-sm text-muted-foreground">Загрузка…</p>}
      {query.isError && <Alert variant="error">{errorMessage(query.error)}</Alert>}

      {query.data && (
        <>
          {query.data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Решений пока нет.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th className="w-24">ID</th>
                  <th className="w-24">Язык</th>
                  <th className="w-56">Статус</th>
                  <th className="w-24">Тесты</th>
                  <th className="w-44">Отправлено</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link to={`/submissions/${item.id}`} className="font-mono text-xs">
                        {item.id.slice(0, 8)}
                      </Link>
                    </td>
                    <td>{LANGUAGE_LABELS[item.language]}</td>
                    <td>
                      <Badge variant={submissionVariant(item.status)}>
                        {submissionLabel(item.status)}
                      </Badge>
                    </td>
                    <td>
                      {item.passed_tests}/{item.total_tests}
                    </td>
                    <td>{formatDateTime(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
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
