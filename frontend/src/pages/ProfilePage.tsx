import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/api/errors";
import { linkTelegram } from "@/api/notifications";
import { myRating } from "@/api/rating";
import { updateProfile } from "@/api/users";
import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/form";

const schema = z.object({
  name: z.string().trim().min(1, "Введите имя").max(100, "Не более 100 символов"),
  avatar_url: z
    .string()
    .trim()
    .refine((value) => value === "" || /^https?:\/\//.test(value), "Укажите ссылку http(s)")
    .optional(),
});

type FormValues = z.infer<typeof schema>;

export function ProfilePage() {
  const { user, reload } = useAuth();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: user?.name ?? "", avatar_url: user?.avatar_url ?? "" },
  });

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      updateProfile({
        name: values.name,
        avatar_url: values.avatar_url?.trim() ? values.avatar_url : null,
      }),
    onSuccess: () => reload(),
  });

  const telegram = useMutation({ mutationFn: linkTelegram });

  const rating = useQuery({ queryKey: ["rating", "me"], queryFn: () => myRating() });

  async function onSubmit(values: FormValues) {
    await save.mutateAsync(values).catch(() => undefined);
  }

  return (
    <div className="mx-auto max-w-lg space-y-5">
      <Card title="Профиль">
        <form className="space-y-3" onSubmit={handleSubmit(onSubmit)} noValidate>
          {save.isError && <Alert variant="error">{errorMessage(save.error)}</Alert>}
          {save.isSuccess && <Alert variant="success">Профиль сохранён.</Alert>}
          <div>
            <Label htmlFor="name">Имя</Label>
            <Input id="name" {...register("name")} />
            <FieldError>{errors.name?.message}</FieldError>
          </div>
          <div>
            <Label htmlFor="avatar_url">Ссылка на аватар</Label>
            <Input id="avatar_url" placeholder="https://…" {...register("avatar_url")} />
            <FieldError>{errors.avatar_url?.message}</FieldError>
          </div>
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Email</dt>
            <dd>{user?.email}</dd>
            <dt className="text-muted-foreground">Роль</dt>
            <dd>{user?.role}</dd>
          </dl>
          <Button type="submit" disabled={isSubmitting || save.isPending}>
            Сохранить
          </Button>
        </form>
      </Card>

      <Card title="Рейтинг">
        {rating.isLoading ? (
          <p className="text-sm text-muted-foreground">Загрузка…</p>
        ) : rating.data ? (
          <p className="text-sm">
            Место {rating.data.place} · решено {rating.data.solved} · штраф {rating.data.penalty}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Пока нет результатов: отправьте хотя бы одно решение.
          </p>
        )}
      </Card>

      <Card title="Telegram">
        <div className="space-y-3 text-sm">
          {telegram.isError && <Alert variant="error">{errorMessage(telegram.error)}</Alert>}
          {telegram.data ? (
            <div className="space-y-1">
              <p>Код действует 10 минут.</p>
              {telegram.data.url ? (
                <p>
                  Откройте{" "}
                  <a href={telegram.data.url} target="_blank" rel="noreferrer">
                    бота в Telegram
                  </a>{" "}
                  и нажмите Start.
                </p>
              ) : (
                <p>
                  Отправьте боту команду{" "}
                  <code className="font-mono">/start {telegram.data.code}</code>.
                </p>
              )}
            </div>
          ) : (
            <>
              <p className="text-muted-foreground">
                Привяжите Telegram, чтобы получать уведомления о начале и завершении конкурсов и о
                вердиктах.
              </p>
              <Button
                variant="secondary"
                disabled={telegram.isPending}
                onClick={() => telegram.mutate()}
              >
                Получить код привязки
              </Button>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
