import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/api/errors";
import { linkTelegram, telegramStatus } from "@/api/notifications";
import { myRating } from "@/api/rating";
import { updateProfile } from "@/api/users";
import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/form";
import { formatDateTime } from "@/lib/format";

const schema = z.object({
  name: z.string().trim().min(1, "Введите имя").max(100, "Не более 100 символов"),
  avatar_url: z
    .string()
    .trim()
    .refine((value) => value === "" || /^https?:\/\//.test(value), "Укажите ссылку http(s)")
    .optional(),
});

type FormValues = z.infer<typeof schema>;

function ProfilePhoto({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);

  if (failed || !/^https?:\/\//i.test(url)) {
    return <p className="text-sm text-muted-foreground" role="status">
      Не удалось загрузить фото. Укажите прямую ссылку на изображение.
    </p>;
  }

  return (
    <img
      src={url}
      alt="Фотография профиля"
      width={80}
      height={80}
      className="h-20 w-20 rounded-full object-cover"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

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

  const linkStatus = useQuery({
    queryKey: ["telegram", "status", user?.id],
    queryFn: telegramStatus,
    enabled: Boolean(user),
    staleTime: 0,
    refetchOnWindowFocus: true,
  });

  const telegram = useMutation({
    mutationFn: async () => ({
      ...(await linkTelegram()),
      previousLink: linkStatus.data?.linked_at ?? null,
    }),
  });
  const awaitingLink = telegram.data?.previousLink === (linkStatus.data?.linked_at ?? null);

  const rating = useQuery({
    queryKey: ["rating", "me", user?.id],
    queryFn: () => myRating(),
    enabled: Boolean(user),
    staleTime: 0,
  });

  async function onSubmit(values: FormValues) {
    await save.mutateAsync(values).catch(() => undefined);
  }

  return (
    <div className="mx-auto max-w-lg space-y-5">
      <Card title="Профиль">
        <form className="space-y-3" onSubmit={handleSubmit(onSubmit)} noValidate>
          {save.isError && <Alert variant="error">{errorMessage(save.error)}</Alert>}
          {save.isSuccess && <Alert variant="success">Профиль сохранён.</Alert>}
          {user?.avatar_url && <ProfilePhoto key={user.avatar_url} url={user.avatar_url} />}
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
        ) : rating.isError ? (
          <Alert variant="error">{errorMessage(rating.error)}</Alert>
        ) : (
          <dl className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <dt className="text-muted-foreground">Решено задач</dt>
              <dd className="text-lg font-semibold">{rating.data?.solved ?? 0}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Место</dt>
              <dd className="text-lg">{rating.data?.place ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Штраф, мин</dt>
              <dd className="text-lg">{rating.data?.penalty ?? 0}</dd>
            </div>
          </dl>
        )}
      </Card>

      <Card title="Telegram">
        <div className="space-y-3 text-sm">
          {telegram.isError && <Alert variant="error">{errorMessage(telegram.error)}</Alert>}
          {linkStatus.isError && <Alert variant="error">{errorMessage(linkStatus.error)}</Alert>}
          {linkStatus.data?.linked && (
            <>
              <Alert variant="success">Telegram привязан.</Alert>
              {linkStatus.data.name || linkStatus.data.username ? (
                <p>
                  {linkStatus.data.name} {linkStatus.data.username && `@${linkStatus.data.username}`}
                </p>
              ) : (
                <p>Чтобы увидеть имя аккаунта, отправьте боту <code>/profile</code> и обновите страницу.</p>
              )}
              {linkStatus.data.linked_at && <p>Дата привязки: {formatDateTime(linkStatus.data.linked_at)}</p>}
            </>
          )}
          {telegram.data && awaitingLink ? (
            <div className="space-y-1">
              <p>Код действует {Math.ceil(telegram.data.expires_in / 60)} мин. с момента выдачи.</p>
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
              <div className="flex gap-3">
                <Button
                  variant="secondary"
                  disabled={linkStatus.isFetching}
                  onClick={() => void linkStatus.refetch()}
                >
                  Проверить привязку
                </Button>
                <Button
                  variant="secondary"
                  disabled={telegram.isPending}
                  onClick={() => telegram.mutate()}
                >
                  Получить новый код
                </Button>
              </div>
            </div>
          ) : (
            <>
              {!linkStatus.data?.linked && (
                <p className="text-muted-foreground">
                  Привяжите Telegram, чтобы получать уведомления о начале и завершении конкурсов и о
                  вердиктах.
                </p>
              )}
              <Button
                variant="secondary"
                disabled={telegram.isPending}
                onClick={() => telegram.mutate()}
              >
                {linkStatus.data?.linked ? "Привязать другой чат" : "Получить код привязки"}
              </Button>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
