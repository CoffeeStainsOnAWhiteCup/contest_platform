import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import {
  createTest,
  deleteTest,
  getProblem,
  importTests,
  listTests,
  updateTest,
} from "@/api/problems";
import type { TestRead } from "@/api/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/form";

type Draft = {
  input_data: string;
  expected_output: string;
  is_sample: boolean;
  ordinal: string;
};

const EMPTY: Draft = { input_data: "", expected_output: "", is_sample: false, ordinal: "" };

function importError(error: unknown): string {
  const status = (error as { status?: number }).status;
  if (status === 409) return "В файле повторяются явно заданные номера тестов.";
  if (status === 413) return "Файл больше 5 МиБ.";
  if (status === 415) return "Поддерживаются только JSON и CSV.";
  if (status === 422) return "Не удалось разобрать файл: проверьте формат.";
  return errorMessage(error);
}

export function AdminTestsPage() {
  const { problemId = "" } = useParams();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const problem = useQuery({
    queryKey: ["problem", problemId],
    queryFn: () => getProblem(problemId),
    enabled: Boolean(problemId),
  });

  const tests = useQuery({
    queryKey: ["tests", problemId],
    queryFn: () => listTests(problemId),
    enabled: Boolean(problemId),
  });

  function reset() {
    setDraft(EMPTY);
    setEditingId(null);
  }

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["tests", problemId] });
    queryClient.invalidateQueries({ queryKey: ["problem", problemId] });
  }

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        input_data: draft.input_data,
        expected_output: draft.expected_output,
        is_sample: draft.is_sample,
        ...(draft.ordinal.trim() ? { ordinal: Number(draft.ordinal) } : {}),
      };
      return editingId
        ? updateTest(problemId, editingId, payload)
        : createTest(problemId, payload);
    },
    onSuccess: () => {
      setNotice(editingId ? "Тест обновлён." : "Тест добавлен.");
      reset();
      invalidate();
    },
  });

  const remove = useMutation({
    mutationFn: (testId: string) => deleteTest(problemId, testId),
    onSuccess: () => invalidate(),
  });

  const upload = useMutation({
    mutationFn: (file: File) => importTests(problemId, file),
    onSuccess: (result) => {
      setNotice(`Импортировано тестов: ${result.imported}.`);
      invalidate();
    },
  });

  function startEdit(test: TestRead) {
    setEditingId(test.id);
    setDraft({
      input_data: test.input_data,
      expected_output: test.expected_output,
      is_sample: test.is_sample,
      ordinal: String(test.ordinal),
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">
          Тесты{problem.data ? `: ${problem.data.title}` : ""}
        </h1>
        {problem.data && (
          <Link to={`/contests/${problem.data.contest_id}`} className="text-sm">
            К конкурсу
          </Link>
        )}
      </div>

      {notice && <Alert variant="success">{notice}</Alert>}
      {save.isError && <Alert variant="error">{errorMessage(save.error)}</Alert>}
      {remove.isError && <Alert variant="error">{errorMessage(remove.error)}</Alert>}
      {upload.isError && <Alert variant="error">{importError(upload.error)}</Alert>}

      <Card title={editingId ? "Изменить тест" : "Добавить тест"}>
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="input">Ввод</Label>
              <Textarea
                id="input"
                className="min-h-32 font-mono text-xs"
                value={draft.input_data}
                onChange={(event) => setDraft({ ...draft, input_data: event.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="output">Ожидаемый вывод</Label>
              <Textarea
                id="output"
                className="min-h-32 font-mono text-xs"
                value={draft.expected_output}
                onChange={(event) => setDraft({ ...draft, expected_output: event.target.value })}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-28">
              <Label htmlFor="ordinal">Номер</Label>
              <Input
                id="ordinal"
                type="number"
                value={draft.ordinal}
                onChange={(event) => setDraft({ ...draft, ordinal: event.target.value })}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={draft.is_sample}
                onChange={(event) => setDraft({ ...draft, is_sample: event.target.checked })}
              />
              Пример
            </label>
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {editingId ? "Сохранить" : "Добавить"}
            </Button>
            {editingId && (
              <Button variant="secondary" onClick={reset}>
                Отмена
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Card
        title="Импорт из файла"
        actions={
          <label className="cursor-pointer text-sm text-primary">
            Загрузить JSON или CSV
            <input
              type="file"
              accept=".json,.csv"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  upload.mutate(file);
                }
                event.target.value = "";
              }}
            />
          </label>
        }
      >
        <p className="text-sm text-muted-foreground">
          До 5 МиБ и 1000 тестов за раз. При повторной загрузке с явными номерами вернётся
          конфликт.
        </p>
      </Card>

      <Card title="Тесты">
        {tests.isLoading ? (
          <p className="text-sm text-muted-foreground">Загрузка…</p>
        ) : tests.data && tests.data.length > 0 ? (
          <div className="space-y-3">
            {tests.data.map((test) => (
              <div key={test.id} className="rounded border border-border p-3">
                <div className="mb-2 flex items-center gap-3 text-sm">
                  <span className="font-medium">Тест {test.ordinal}</span>
                  {test.is_sample && <span className="text-muted-foreground">пример</span>}
                  <button
                    type="button"
                    className="ml-auto text-sm"
                    onClick={() => startEdit(test)}
                  >
                    Изменить
                  </button>
                  <button
                    type="button"
                    className="text-sm text-danger"
                    onClick={() => remove.mutate(test.id)}
                  >
                    Удалить
                  </button>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <pre className="overflow-x-auto rounded border border-border bg-muted p-2 font-mono text-xs">
                    {test.input_data || " "}
                  </pre>
                  <pre className="overflow-x-auto rounded border border-border bg-muted p-2 font-mono text-xs">
                    {test.expected_output || " "}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Тестов нет.</p>
        )}
      </Card>
    </div>
  );
}
