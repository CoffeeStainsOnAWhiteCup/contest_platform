import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { createProblem } from "@/api/contests";
import { errorMessage } from "@/api/errors";
import { deleteProblem, getProblem, updateProblem } from "@/api/problems";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldError, Input, Label, Textarea } from "@/components/ui/form";

const schema = z.object({
  title: z.string().trim().min(1, "Введите название").max(255, "Не более 255 символов"),
  statement: z.string().trim().min(1, "Введите условие"),
  time_limit_ms: z.number({ invalid_type_error: "Введите число" }).int().min(1, "Минимум 1"),
  memory_limit_mb: z.number({ invalid_type_error: "Введите число" }).int().min(1, "Минимум 1"),
  ordinal: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function ProblemFormPage() {
  const { contestId, problemId } = useParams();
  const editing = Boolean(problemId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["problem", problemId],
    queryFn: () => getProblem(problemId as string),
    enabled: editing,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      statement: "",
      time_limit_ms: 1000,
      memory_limit_mb: 256,
      ordinal: "",
    },
  });

  useEffect(() => {
    if (query.data) {
      reset({
        title: query.data.title,
        statement: query.data.statement,
        time_limit_ms: query.data.time_limit_ms,
        memory_limit_mb: query.data.memory_limit_mb,
        ordinal: String(query.data.ordinal),
      });
    }
  }, [query.data, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        title: values.title,
        statement: values.statement,
        time_limit_ms: values.time_limit_ms,
        memory_limit_mb: values.memory_limit_mb,
        ...(values.ordinal && values.ordinal.trim() ? { ordinal: Number(values.ordinal) } : {}),
      };
      return editing
        ? updateProblem(problemId as string, payload)
        : createProblem(contestId as string, payload);
    },
    onSuccess: (problem) => {
      queryClient.setQueryData(["problem", problem.id], problem);
      queryClient.invalidateQueries({ queryKey: ["contest", problem.contest_id] });
      navigate(`/contests/${problem.contest_id}`);
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteProblem(problemId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contest", query.data?.contest_id] });
      navigate(`/contests/${query.data?.contest_id}`);
    },
  });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      await mutation.mutateAsync(values);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const cancelTo = editing ? `/contests/${query.data?.contest_id ?? ""}` : `/contests/${contestId}`;

  return (
    <div className="mx-auto max-w-lg">
      <Card title={editing ? "Изменить задачу" : "Новая задача"}>
        {editing && query.isLoading ? (
          <p className="text-sm text-muted-foreground">Загрузка…</p>
        ) : (
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)} noValidate>
            {error && <Alert variant="error">{error}</Alert>}
            {remove.isError && <Alert variant="error">{errorMessage(remove.error)}</Alert>}
            <div>
              <Label htmlFor="title">Название</Label>
              <Input id="title" {...register("title")} />
              <FieldError>{errors.title?.message}</FieldError>
            </div>
            <div>
              <Label htmlFor="statement">Условие</Label>
              <Textarea
                id="statement"
                className="min-h-48"
                {...register("statement")}
              />
              <FieldError>{errors.statement?.message}</FieldError>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="time_limit_ms">Время, мс</Label>
                <Input
                  id="time_limit_ms"
                  type="number"
                  {...register("time_limit_ms", { valueAsNumber: true })}
                />
                <FieldError>{errors.time_limit_ms?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="memory_limit_mb">Память, МБ</Label>
                <Input
                  id="memory_limit_mb"
                  type="number"
                  {...register("memory_limit_mb", { valueAsNumber: true })}
                />
                <FieldError>{errors.memory_limit_mb?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="ordinal">Номер</Label>
                <Input id="ordinal" type="number" {...register("ordinal")} />
                <FieldError>{errors.ordinal?.message}</FieldError>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={isSubmitting}>
                {editing ? "Сохранить" : "Создать"}
              </Button>
              <Link to={cancelTo} className="text-sm">
                Отмена
              </Link>
              {editing && (
                <>
                  <Link to={`/admin/problems/${problemId}/tests`} className="text-sm">
                    Тесты
                  </Link>
                  <button
                    type="button"
                    className="ml-auto text-sm text-danger"
                    onClick={() => {
                      if (window.confirm("Удалить задачу?")) {
                        remove.mutate();
                      }
                    }}
                  >
                    Удалить задачу
                  </button>
                </>
              )}
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
