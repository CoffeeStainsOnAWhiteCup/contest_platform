import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { createContest, getContest, updateContest } from "@/api/contests";
import { errorMessage } from "@/api/errors";
import type { ContestStatus } from "@/api/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldError, Input, Label, Select, Textarea } from "@/components/ui/form";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import { submitDenial } from "@/lib/contestWindow";
import { contestStatusLabel } from "@/lib/labels";

const STATUSES: ContestStatus[] = ["draft", "published", "active", "finished", "archived"];

const schema = z
  .object({
    title: z.string().trim().min(1, "Введите название").max(255, "Не более 255 символов"),
    description: z.string().optional(),
    start_at: z.string().min(1, "Укажите начало"),
    end_at: z.string().min(1, "Укажите конец"),
    status: z.enum(["draft", "published", "active", "finished", "archived"]),
  })
  .refine((data) => new Date(data.end_at) > new Date(data.start_at), {
    path: ["end_at"],
    message: "Конец должен быть позже начала",
  });

type FormValues = z.infer<typeof schema>;

export function ContestFormPage() {
  const { contestId } = useParams();
  const editing = Boolean(contestId);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["contest", contestId],
    queryFn: () => getContest(contestId as string),
    enabled: editing,
  });

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", description: "", start_at: "", end_at: "", status: "draft" },
  });

  useEffect(() => {
    if (query.data) {
      reset({
        title: query.data.title,
        description: query.data.description ?? "",
        start_at: toLocalInput(query.data.start_at),
        end_at: toLocalInput(query.data.end_at),
        status: query.data.status,
      });
    }
  }, [query.data, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        title: values.title,
        description: values.description?.trim() ? values.description : null,
        start_at: fromLocalInput(values.start_at),
        end_at: fromLocalInput(values.end_at),
        status: values.status,
      };
      return editing
        ? updateContest(contestId as string, payload)
        : createContest(payload);
    },
    onSuccess: (contest) => {
      void queryClient.invalidateQueries({ queryKey: ["contests"] });
      void queryClient.invalidateQueries({ queryKey: ["contest", contest.id] });
      navigate(`/contests/${contest.id}`);
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

  const status = watch("status");
  const startAt = watch("start_at");
  const endAt = watch("end_at");
  const windowWarning = useMemo(() => {
    if (status !== "active" || !startAt || !endAt) {
      return null;
    }
    return submitDenial({ status, start_at: startAt, end_at: endAt });
  }, [status, startAt, endAt]);

  function setActiveNow() {
    const now = new Date();
    setValue("start_at", toLocalInput(now.toISOString()), { shouldValidate: true });
    const currentEnd = getValues("end_at");
    if (!currentEnd || Date.parse(currentEnd) <= now.getTime()) {
      setValue("end_at", toLocalInput(new Date(now.getTime() + 3_600_000).toISOString()), {
        shouldValidate: true,
      });
    }
    setValue("status", "active", { shouldValidate: true });
  }

  return (
    <div className="mx-auto max-w-lg">
      <Card title={editing ? "Изменить конкурс" : "Новый конкурс"}>
        {editing && query.isLoading ? (
          <p className="text-sm text-muted-foreground">Загрузка…</p>
        ) : (
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)} noValidate>
            {error && <Alert variant="error">{error}</Alert>}
            {windowWarning && (
              <Alert variant="warning">
                Статус «Идёт», но интервал не включает текущее время — участники не смогут
                отправлять решения. Исправьте начало и конец или нажмите «Активно сейчас».
              </Alert>
            )}
            <div>
              <Label htmlFor="title">Название</Label>
              <Input id="title" {...register("title")} />
              <FieldError>{errors.title?.message}</FieldError>
            </div>
            <div>
              <Label htmlFor="description">Описание</Label>
              <Textarea id="description" {...register("description")} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="start_at">Начало</Label>
                <Input id="start_at" type="datetime-local" {...register("start_at")} />
                <FieldError>{errors.start_at?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="end_at">Конец</Label>
                <Input id="end_at" type="datetime-local" {...register("end_at")} />
                <FieldError>{errors.end_at?.message}</FieldError>
              </div>
            </div>
            <div className="w-48">
              <Label htmlFor="status">Статус</Label>
              <Select id="status" {...register("status")}>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {contestStatusLabel(status)}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Button variant="secondary" size="sm" onClick={setActiveNow}>
                Активно сейчас
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={isSubmitting}>
                {editing ? "Сохранить" : "Создать"}
              </Button>
              <Link to="/admin/contests" className="text-sm">
                Отмена
              </Link>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
